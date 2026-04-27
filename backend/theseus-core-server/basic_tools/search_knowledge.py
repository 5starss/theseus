import json
from src.db.postgres import SessionLocal
from src.knowledge.service import KnowledgeService

def run(project_id: str, query: str, top_k: int = 5) -> str:
    """
    RAG 기반의 지식 검색 툴입니다.
    주어진 query와 가장 유사한 프로젝트 내부의 문서 조각(chunk)을 찾아 반환합니다.
    """
    db = SessionLocal()
    try:
        service = KnowledgeService(db)
        results = service.search_knowledge(project_id=project_id, query=query, top_k=top_k)
        
        if not results:
            return "검색 결과가 없습니다."
            
        formatted_results = []
        for i, res in enumerate(results, 1):
            formatted_results.append({
                "rank": i,
                "title": res.title,
                "source": res.source_uri,
                "score": round(res.similarity_score, 4),
                "content": res.content
            })
            
        return json.dumps(formatted_results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"검색 중 오류가 발생했습니다: {str(e)}"
    finally:
        db.close()

if __name__ == "__main__":
    # 간단한 테스트 실행
    # python -m basic_tools.search_knowledge
    print(run("test_project_id", "테스트 쿼리입니다."))
