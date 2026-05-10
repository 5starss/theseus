"""Tool Retriever: 사용자 요청에 따라 가장 관련성 높은 도구를 인메모리 시맨틱 검색으로 추출합니다.

PostgreSQL 등 외부 인프라 의존 없이, intfloat/multilingual-e5-small 임베딩과
numpy 코사인 유사도를 사용하여 경량으로 동작합니다.

핵심 설계 원칙:
- **비대칭 검색(Asymmetric Search)**: 사용자의 짧은 쿼리와 도구의 긴 설명을
  E5 모델의 `query:`/`passage:` 프리픽스로 정확히 매핑합니다.
- **Few-shot 쿼리 보강**: 도구 설명에 예상 사용자 발화를 추가하여
  임베딩 공간에서의 매칭 품질을 극대화합니다.
- **필수 도구 보장(Essential Tools)**: 검색 결과와 무관하게 핵심 도구를
  항상 포함하여 에이전트의 최소 동작을 보장합니다.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
from theseus_engine.tools.core.base_tools import BaseTool, ToolRegistry

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adaptive K: 쿼리 복잡도 기반 동적 슬롯 조정
# ---------------------------------------------------------------------------

# 복잡도 신호 패턴 (한/영 혼용)
_MULTI_STEP_PATTERNS = re.compile(
    r"(그리고|그런 다음|그 다음|이후에|마지막으로|먼저|첫째|둘째|셋째"
    r"|and then|after that|finally|first|second|step \d|(\d+)[.)]\s)",
    re.IGNORECASE,
)
_COMPLEX_KEYWORDS = re.compile(
    r"(분석|리팩터링|마이그레이션|아키텍처|전체|모든|프로젝트 전반"
    r"|analyze|refactor|migrat|architect|entire|all files|project.wide)",
    re.IGNORECASE,
)
_SIMPLE_KEYWORDS = re.compile(
    r"(뭐야|뭔가요|알려줘|설명해줘|무엇|어떻게"
    r"|what is|what's|explain|tell me|how does)",
    re.IGNORECASE,
)


def compute_adaptive_k(query: str, base_k: int = 8) -> int:
    """쿼리 복잡도를 분석하여 최적 K 값을 반환합니다.

    - 단순 질문 → base_k // 2  (최소 3)
    - 다단계/복합 요청 → base_k * 1.5  (최대 16)
    - 그 외 → base_k

    Args:
        query: 사용자 입력 텍스트.
        base_k: 기본 K 값 (기본 8).

    Returns:
        조정된 K 정수 값.
    """
    tokens = query.split()
    word_count = len(tokens)

    multi_step_hits = len(_MULTI_STEP_PATTERNS.findall(query))
    complex_hits = len(_COMPLEX_KEYWORDS.findall(query))
    simple_hits = len(_SIMPLE_KEYWORDS.findall(query))

    # 가중 점수
    score = 0
    score += multi_step_hits * 2
    score += complex_hits * 1
    score -= simple_hits * 1
    if word_count > 30:
        score += 2
    elif word_count < 8:
        score -= 1

    if score >= 3:
        k = int(base_k * 1.5)
    elif score <= -1:
        k = max(3, base_k // 2)
    else:
        k = base_k

    # 상한/하한 클램프
    k = max(3, min(k, 16))
    log.debug(
        "[AdaptiveK] query_len=%d score=%d → k=%d (base=%d)",
        word_count, score, k, base_k,
    )
    return k


# ---------------------------------------------------------------------------
# 항상 포함되어야 하는 필수 도구 이름
# k(유사도 슬롯)와 무관하게 항상 포함됩니다.
# ---------------------------------------------------------------------------
ESSENTIAL_TOOL_NAMES = {
    "read_file",
    "write_file",
    "edit_file",
    "glob",
    "grep",
    "bash",
    "ask_user",
    "create_tool",
}

# 유사도 점수가 이 값 미만인 도구는 반환하지 않음
SIMILARITY_THRESHOLD = 0.3


# ---------------------------------------------------------------------------
# Few-shot 쿼리 보강 맵
# 도구 이름 → 예상 사용자 발화 리스트
# 이 발화들이 passage 텍스트에 함께 임베딩되어 매칭 품질을 높입니다.
# ---------------------------------------------------------------------------
TOOL_EXAMPLE_QUERIES: Dict[str, List[str]] = {
    "web_search": [
        "검색해줘", "최신 뉴스 찾아줘",
        "이 에러 해결법 검색", "공식 문서 찾아줘",
        "구글에서 찾아봐", "인터넷에서 검색",
        "search for", "look up online",
    ],
    "web_fetch": [
        "이 URL 내용 읽어줘", "웹페이지 가져와",
        "문서 다운로드해줘", "링크 열어줘",
        "API 응답 확인해줘", "fetch this URL",
    ],
    "read_file": [
        "이 파일 읽어줘", "코드 보여줘",
        "설정 파일 내용 확인해줘", "파일 열어봐",
        "소스코드 확인", "내용 보여줘",
        "show me the file", "read this",
    ],
    "write_file": [
        "새 파일 만들어줘", "이 내용으로 저장해줘",
        "파일 생성해줘", "새로 작성해줘",
        "create a new file", "save to file",
    ],
    "edit_file": [
        "코드 수정해줘", "버그 고쳐줘",
        "함수 이름 변경해줘", "import 추가해줘",
        "이 부분 바꿔줘", "리팩터링해줘",
        "fix this code", "modify the function",
    ],
    "bash": [
        "터미널 명령 실행해줘", "테스트 실행해줘",
        "패키지 설치해줘", "빌드해줘",
        "서버 실행해줘", "프로세스 확인해줘",
        "pip install", "npm run", "docker",
        "git 명령", "run command", "execute",
    ],
    "lsp": [
        "함수 정의 위치 알려줘", "이 변수 어디서 사용돼?",
        "참조 찾기", "심볼 검색해줘",
        "go to definition", "find references",
        "타입 정보 알려줘", "호출하는 곳 찾아줘",
    ],
    "grep": [
        "이 텍스트가 어디 있어?", "TODO 찾아줘",
        "에러 메시지 검색해줘", "코드에서 이거 찾아줘",
        "어디서 import 하고 있어?", "문자열 검색",
        "find in files", "search for text",
    ],
    "glob": [
        "파일 목록 보여줘", "py 파일 찾아줘",
        "디렉토리 구조 확인", "어떤 파일들이 있어?",
        "프로젝트 구조 보여줘", "list files",
        "find files matching", "show directory",
    ],
    "ask_user": [
        "사용자한테 물어봐", "확인이 필요해",
        "어떤 걸 선택할지 질문해줘",
        "사용자 입력 받아줘", "선택지 제시해줘",
    ],
    "search_knowledge_base": [
        "지식베이스 검색", "이전 프로젝트에서 어떻게 했어?",
        "사내 문서 찾아줘", "기억하고 있는 거 찾아줘",
        "관련 지식 검색", "knowledge search",
    ],
    "ingest_document": [
        "이 정보 기억해줘", "지식베이스에 추가해줘",
        "문서 저장해줘", "나중에 쓸 수 있게 저장",
        "save to knowledge base",
    ],
    "skill_save": [
        "이 방법 기억해줘", "스킬로 저장해줘",
        "워크플로우 저장", "재사용할 수 있게 저장",
    ],
    "skill_read": [
        "저장된 스킬 보여줘", "이전에 배운 방법 알려줘",
        "스킬 내용 확인",
    ],
    "skill_list": [
        "스킬 목록", "배운 것들 보여줘",
        "어떤 스킬이 있어?",
    ],
    "create_tool": [
        "새 도구 만들어줘", "커스텀 툴 생성",
        "도구 제작해줘", "플러그인 만들어줘",
    ],
    "agent": [
        "서브 에이전트 실행", "이 작업 위임해줘",
        "병렬로 처리해줘", "다른 에이전트한테 맡겨줘",
    ],
    "enter_worktree": [
        "실험용 브랜치 만들어줘", "워크트리 생성",
        "안전하게 코드 수정할 공간 만들어줘",
        "격리된 환경에서 작업",
    ],
    "exit_worktree": [
        "워크트리 제거", "실험 브랜치 정리해줘",
        "워크트리 나가기",
    ],
    "brief": [
        "요약해줘", "긴 대화 압축해줘",
        "지금까지 내용 정리해줘", "컨텍스트 줄여줘",
    ],
}


class ToolRetriever:
    """도구 설명을 인메모리 벡터로 관리하여 시맨틱 검색을 수행합니다.

    intfloat/multilingual-e5-small 모델을 1회 로드한 뒤,
    등록된 모든 도구의 (name + description + few-shot queries) 텍스트를
    `passage:` 프리픽스와 함께 임베딩합니다.
    사용자 쿼리는 `query:` 프리픽스를 붙여 비대칭 검색을 수행합니다.
    """

    _instance: Optional["ToolRetriever"] = None
    _init_lock: asyncio.Lock = None  # 인스턴스 생성 전 None, 첫 사용 시 초기화

    # --- Singleton ---------------------------------------------------
    def __new__(cls, full_registry: ToolRegistry):  # noqa: ARG003
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._is_ready = False
            cls._instance = inst
        return cls._instance

    def __init__(self, full_registry: ToolRegistry) -> None:
        if self._is_ready:
            return

        self._full_registry = full_registry
        self._model = None          # SentenceTransformer (lazy)
        self._tool_names: List[str] = []
        self._tool_embeddings: Optional[np.ndarray] = None
        self._index_lock: Optional[asyncio.Lock] = None  # 재인덱싱용 Lock (async 컨텍스트에서 초기화)

        # 쿼리 임베딩 결과 캐시 (query_text → np.ndarray), 최대 128개
        self._query_cache: Dict[str, np.ndarray] = {}
        self._query_cache_order: List[str] = []
        self._QUERY_CACHE_MAX = 128

        # 피드백 로그를 TOOL_EXAMPLE_QUERIES에 병합 (런타임 보강)
        self._effective_examples = self._load_effective_examples()
        self._is_ready = True

    def _get_index_lock(self) -> asyncio.Lock:
        """이벤트 루프 컨텍스트 안에서 Lock을 지연 초기화합니다."""
        if self._index_lock is None:
            self._index_lock = asyncio.Lock()
        return self._index_lock

    @staticmethod
    def _load_effective_examples() -> Dict[str, List[str]]:
        """기본 few-shot 예시에 누적 피드백 로그를 병합합니다."""
        try:
            from theseus_engine.core.tool_usage_logger import merge_feedback_into_examples
            return merge_feedback_into_examples(TOOL_EXAMPLE_QUERIES)
        except Exception as e:
            log.debug("[ToolRetriever] 피드백 로드 실패 (무시): %s", e)
            return TOOL_EXAMPLE_QUERIES

    # --- lazy model load ---------------------------------------------
    def _load_model(self) -> None:
        """multilingual-e5-small 모델을 한 번만 로드합니다."""
        if self._model is not None:
            return
        try:
            import logging as _logging
            # transformers/sentence_transformers 내부 로거의
            # 'Loading weights' 출력 억제
            for _noisy_logger in (
                "sentence_transformers",
                "transformers",
                "huggingface_hub",
            ):
                _logging.getLogger(_noisy_logger).setLevel(
                    _logging.ERROR
                )

            from sentence_transformers import SentenceTransformer

            model_name = "intfloat/multilingual-e5-small"
            self._model = SentenceTransformer(
                model_name,
                device="cpu",        # GPU 없는 환경 명시
            )
            log.info(
                "[ToolRetriever] 임베딩 모델 로드 완료: %s",
                model_name,
            )
        except ImportError:
            log.error(
                "[ToolRetriever] sentence-transformers 패키지가 "
                "없습니다. pip install sentence-transformers 를 "
                "실행하세요."
            )
            raise


    # --- query embedding cache ----------------------------------------
    def _get_cached_query_vec(self, query_text: str) -> Optional[np.ndarray]:
        return self._query_cache.get(query_text)

    def _put_cached_query_vec(self, query_text: str, vec: np.ndarray) -> None:
        if query_text in self._query_cache:
            self._query_cache_order.remove(query_text)
        elif len(self._query_cache) >= self._QUERY_CACHE_MAX:
            oldest = self._query_cache_order.pop(0)
            del self._query_cache[oldest]
        self._query_cache[query_text] = vec
        self._query_cache_order.append(query_text)

    # --- indexing -----------------------------------------------------
    def _build_passage_text(self, tool: BaseTool) -> str:
        """도구의 임베딩용 passage 텍스트를 구성합니다.

        `passage:` 프리픽스 + 도구 이름/설명 + Few-shot 예시 쿼리를
        결합하여 비대칭 검색에 최적화된 텍스트를 생성합니다.

        Args:
            tool: 텍스트를 생성할 BaseTool 인스턴스.

        Returns:
            E5 모델용 passage 텍스트 문자열.
        """
        # 1) 하드코딩된 코어 도구 예시 + 피드백 누적
        examples: List[str] = list(
            self._effective_examples.get(tool.name, [])
        )
        # 2) 도구 클래스가 직접 선언한 example_queries 속성 병합
        #    (커스텀 툴이 자체 예시를 제공할 수 있도록)
        tool_attr_examples = getattr(tool, "example_queries", None)
        if isinstance(tool_attr_examples, (list, tuple)):
            for q in tool_attr_examples:
                if isinstance(q, str) and q and q not in examples:
                    examples.append(q)

        example_str = ""
        if examples:
            example_str = (
                " 예시 질문: " + ", ".join(examples)
            )
        return (
            f"passage: {tool.name}: {tool.description}"
            f"{example_str}"
        )

    async def _ensure_indexed(self) -> None:
        """등록된 도구 목록과 인덱싱된 목록을 비교하여 필요 시 재인덱싱을 수행합니다.

        asyncio.Lock으로 보호되어 병렬 실행 시 중복 인덱싱을 방지합니다.
        """
        current_tools = self._full_registry.list_tools()

        # 빠른 경로: 도구 이름 집합이 동일하면 재인덱싱 불필요
        # len() 비교만으로는 A 삭제 + B 추가처럼 개수가 같은 교체를 감지 못하므로 set 비교 사용
        if (
            self._tool_embeddings is not None
            and set(t.name for t in current_tools) == set(self._tool_names)
        ):
            return

        async with self._get_index_lock():
            # Lock 획득 후 재확인 (double-checked locking)
            current_tools = self._full_registry.list_tools()
            if (
                self._tool_embeddings is not None
                and set(t.name for t in current_tools) == set(self._tool_names)
            ):
                return

            log.info(
                "[ToolRetriever] 도구 변경 감지 (%d → %d), 재인덱싱 시작.",
                len(self._tool_names), len(current_tools),
            )

            self._load_model()

            texts: List[str] = []
            names: List[str] = []
            for tool in current_tools:
                texts.append(self._build_passage_text(tool))
                names.append(tool.name)

            if not texts:
                log.warning("[ToolRetriever] 등록된 도구가 없습니다.")
                self._tool_names = []
                self._tool_embeddings = np.empty((0, 384))
                return

            embeddings = await asyncio.to_thread(
                self._model.encode,
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._tool_embeddings = np.array(embeddings)
            self._tool_names = names
            # 도구 목록이 바뀌면 쿼리 캐시 무효화
            self._query_cache.clear()
            self._query_cache_order.clear()
            log.info("[ToolRetriever] %d개 도구 인메모리 인덱싱 완료.", len(names))

    # --- history tool extraction ------------------------------------
    @staticmethod
    def _extract_history_tool_names(
        history_messages: List,
    ) -> set[str]:
        """이전 메시지 히스토리에서 사용된 tool_use 이름을 추출합니다.

        ConversationMessage 객체 또는 dict 형식 모두 처리합니다.

        Args:
            history_messages: engine.messages (ConversationMessage 리스트
                              또는 dict 리스트).

        Returns:
            히스토리에서 호출된 도구 이름의 집합.
        """
        used: set[str] = set()
        for m in history_messages:
            # --- ConversationMessage 객체 처리 ---
            if hasattr(m, "tool_uses"):
                for tool_use_block in m.tool_uses:
                    name = getattr(tool_use_block, "name", None)
                    if name:
                        used.add(name)
            # --- dict 형식 처리 (fallback) ---
            elif isinstance(m, dict):
                content = m.get("content", [])
                if not isinstance(content, list):
                    continue
                for c in content:
                    if (
                        isinstance(c, dict)
                        and c.get("type") == "tool_use"
                    ):
                        name = c.get("name", "")
                        if name:
                            used.add(name)
        return used

    # --- retrieval ----------------------------------------------------
    async def retrieve_top_k(
        self,
        query: str,
        full_registry: ToolRegistry,
        k: int = 8,
        history_messages: Optional[List[dict]] = None,
        adaptive: bool = True,
    ) -> List[BaseTool]:
        """사용자 쿼리와 가장 유사한 도구 상위 K개를 반환합니다.

        - 필수 도구(ESSENTIAL_TOOL_NAMES)는 k와 무관하게 항상 포함됩니다.
        - k는 유사도 검색으로 '추가'하는 도구 수를 의미합니다.
        - 히스토리에 등장한 도구도 k와 무관하게 강제 포함합니다.
        - adaptive=True이면 쿼리 복잡도에 따라 k를 자동 조정합니다.

        Args:
            query: 사용자 요청 텍스트.
            full_registry: 최신 전체 도구 레지스트리.
            k: 유사도 검색으로 추가할 기본 도구 수 (필수 도구와 별도 슬롯).
            history_messages: engine.messages 리스트 (선택).
                              전달 시 히스토리에 등장한 도구를 강제 포함.
            adaptive: True이면 compute_adaptive_k()로 k를 동적 조정.

        Returns:
            선별된 BaseTool 인스턴스 리스트.
        """
        from theseus_engine.observability.stats import SessionStats
        _rag_start = time.monotonic()

        self._full_registry = full_registry
        if adaptive:
            k = compute_adaptive_k(query, base_k=k)
            log.info("[ToolRetriever] Adaptive K → %d (query: '%s')", k, query[:40])

        await self._ensure_indexed()

        # 1. 필수 도구 확보 (k 슬롯과 무관)
        selected: List[BaseTool] = []
        seen: set[str] = set()
        for name in ESSENTIAL_TOOL_NAMES:
            tool = self._full_registry.get(name)
            if tool:
                selected.append(tool)
                seen.add(name)

        # 2. 히스토리에 등장한 도구 강제 포함 (Ghost Tool Call 방지, k 슬롯과 무관)
        if history_messages:
            history_tool_names = self._extract_history_tool_names(
                history_messages
            )
            for name in history_tool_names:
                if name not in seen:
                    tool = self._full_registry.get(name)
                    if tool:
                        selected.append(tool)
                        seen.add(name)
                        log.debug(
                            "[ToolRetriever] 히스토리 도구 강제 포함: %s",
                            name,
                        )

        # 3. 임베딩이 비어 있으면 여기까지의 도구만 반환
        if self._tool_embeddings.shape[0] == 0:
            return selected

        # 4. E5 비대칭 검색: query: 프리픽스 부착 (캐시 우선)
        query_text = f"query: {query}"
        query_vec = self._get_cached_query_vec(query_text)
        if query_vec is None:
            query_vec = await asyncio.to_thread(
                self._model.encode,
                query_text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._put_cached_query_vec(query_text, query_vec)
        # 코사인 유사도 (정규화된 벡터의 내적)
        scores = self._tool_embeddings @ query_vec

        # 5. 리랭킹(Re-ranking): 키워드 매칭 기반 점수 보정
        scores = self._rerank_by_keyword(query, scores)

        # 6. 점수 내림차순 정렬 후 유사도 슬롯 k개 추가 (임계값 필터링 적용)
        ranked_indices = np.argsort(scores)[::-1]
        similarity_added = 0

        for idx in ranked_indices:
            if similarity_added >= k:
                break
            score = float(scores[idx])
            if score < SIMILARITY_THRESHOLD:
                log.debug(
                    "[ToolRetriever] 임계값 미달로 중단: %s (score=%.3f < %.3f)",
                    self._tool_names[idx], score, SIMILARITY_THRESHOLD,
                )
                break
            name = self._tool_names[idx]
            if name in seen:
                continue
            tool = self._full_registry.get(name)
            if tool:
                selected.append(tool)
                seen.add(name)
                similarity_added += 1
                log.debug(
                    "[ToolRetriever] 유사도 선택: %s (score=%.3f)",
                    name, score,
                )

        _rag_ms = (time.monotonic() - _rag_start) * 1000
        SessionStats.get().observe("rag.retrieval_ms", _rag_ms)

        log.info(
            "[ToolRetriever] 쿼리='%s' → 선택된 %d개 도구: %s (%.0fms)",
            query[:40],
            len(selected),
            ", ".join(t.name for t in selected),
            _rag_ms,
        )
        return selected

    def _rerank_by_keyword(self, query: str, scores: np.ndarray) -> np.ndarray:
        """키워드 매칭을 기반으로 검색 점수를 보정(Re-ranking)합니다.
        
        사용자 쿼리에 포함된 단어가 도구 이름이나 핵심 키워드와 일치하면
        해당 도구의 점수에 보너스를 부여하여 상단에 노출될 확률을 높입니다.
        """
        boosted_scores = scores.copy()
        query_lower = query.lower()
        
        # 도구별 핵심 키워드 매핑 (리랭킹용)
        keyword_map = {
            "write_file": ["만들어", "작성", "save", "write", "create"],
            "read_file": ["읽어", "열어", "show", "read", "open"],
            "edit_file": ["수정", "바꿔", "fix", "modify", "edit"],
            "grep": ["찾아", "검색", "find", "search", "grep"],
            "web_search": ["구글", "인터넷", "google", "search"],
            "bash": ["터미널", "실행", "command", "run", "execute"],
            "kb": ["지식", "기억", "knowledge", "kb"],
        }
        
        for idx, name in enumerate(self._tool_names):
            # 1) 이름 직접 매칭 보너스
            if name in query_lower:
                boosted_scores[idx] += 0.2
            
            # 2) 키워드 맵 매칭 보너스
            keywords = keyword_map.get(name, [])
            for kw in keywords:
                if kw in query_lower:
                    boosted_scores[idx] += 0.15
                    break # 키워드 보너스는 중복 방지 위해 한 번만
                    
        return boosted_scores


def build_retrieved_registry(
    retrieved_tools: List[BaseTool],
) -> ToolRegistry:
    """검색된 도구 목록으로 새로운 레지스트리를 구성합니다."""
    registry = ToolRegistry()
    for tool in retrieved_tools:
        registry.register(tool)
    return registry

