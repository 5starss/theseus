import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  LineChart,
  Monitor,
  Tablet,
  Smartphone,
  Volume2
} from "lucide-react";
import { Button } from "@/components/ui/button";

// ==========================================
// 1. 외부 순수 헬퍼 함수 및 정적 데이터 정의
// ==========================================

// 실제 실시간 주요 종목 시세 데이터 (제공해주신 실제 캡처본 데이터 기반)
const REALTIME_STOCKS = [
  { rank: 1, name: "LG전자", price: "278,000원", change: "+23.28%" },
  { rank: 2, name: "NAVER", price: "225,750원", change: "+10.12%" },
  { rank: 3, name: "현대차", price: "726,000원", change: "+7.24%" },
  { rank: 4, name: "삼성전자", price: "311,000원", change: "+3.84%" },
  { rank: 5, name: "SK하이닉스", price: "2,357,000원", change: "+2.97%" }
];


// ==========================================
// 2. 메인 컴포넌트 구현
// ==========================================

export default function HomeMockup() {
  // --- 상태 관리 ---

  // 쇼케이스 탭 상태 ("main" | "detail")
  const [showcaseTab, setShowcaseTab] = useState<"main" | "detail">("main");

  // 소셜 프루프 카운팅 수치 상태
  const [userCount, setUserCount] = useState<number>(23000);
  const [analysisCount, setAnalysisCount] = useState<number>(142000);
  const [activeUserCount, setActiveUserCount] = useState<number>(3100);


  // --- 마운트 시 소셜 프루프 카운팅 서서히 상승 애니메이션 ---
  useEffect(() => {
    const duration = 1500;
    const steps = 30;
    const intervalTime = duration / steps;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      setUserCount(Math.round(23000 + (24582 - 23000) * (step / steps)));
      setAnalysisCount(Math.round(142000 + (148290 - 142000) * (step / steps)));
      setActiveUserCount(Math.round(3100 + (3492 - 3100) * (step / steps)));

      if (step >= steps) {
        clearInterval(timer);
      }
    }, intervalTime);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-full min-h-screen bg-gradient-to-b from-[#f4f7ff] via-white to-[#f9fafb] text-[#1e293b] font-sans overflow-x-hidden relative pb-16">

      {/* 🌌 청량감을 더하는 소프트 아쿠아 & 스카이 로얄 블루 네온 오라 백라이트 */}
      <div className="absolute top-[3%] left-[8%] w-[700px] h-[700px] rounded-full bg-blue-400/10 blur-[130px] pointer-events-none" />
      <div className="absolute top-[40%] right-[3%] w-[600px] h-[600px] rounded-full bg-[#155dfc]/5 blur-[125px] pointer-events-none" />
      <div className="absolute bottom-[15%] left-[10%] w-[550px] h-[550px] rounded-full bg-[#38bdf8]/8 blur-[110px] pointer-events-none" />

      {/* 2. 글래스모피즘 프리미엄 라이트 헤더 */}
      <header className="sticky top-0 z-50 h-16 w-full bg-white/70 backdrop-blur-xl border-b border-slate-200/50 px-4 md:px-8 flex items-center justify-between transition-all">
        <div className="flex items-center gap-8">
          <Link to="/mockup" className="flex items-center gap-0 mr-6 group">
            <img src="/ssafy_logo.png" alt="ssafy_logo" className="w-10 h-8 group-hover:scale-105 transition-all" />
            <span className="font-extrabold text-lg text-[#0f172a] tracking-tight">싸피증권</span>
          </Link>

          <nav className="hidden md:flex items-center gap-6">
            <button onClick={() => {
              const el = document.getElementById("trading-demo");
              el?.scrollIntoView({ behavior: "smooth" });
            }} className="text-sm font-semibold text-slate-500 hover:text-[#155dfc] transition-colors cursor-pointer">차트</button>

            <button onClick={() => {
              const el = document.getElementById("trending-themes");
              el?.scrollIntoView({ behavior: "smooth" });
            }} className="text-sm font-semibold text-slate-500 hover:text-[#155dfc] transition-colors cursor-pointer">실시간 데이터 제공</button>

            <button onClick={() => {
              const el = document.getElementById("social-timeline");
              el?.scrollIntoView({ behavior: "smooth" });
            }} className="text-sm font-semibold text-slate-500 hover:text-[#155dfc] transition-colors cursor-pointer">커뮤니티</button>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" className="h-9 px-4 text-slate-600 hover:text-[#155dfc] hover:bg-slate-100 font-semibold text-sm">
            <Link to="/login">로그인</Link>
          </Button>
          <Button asChild className="h-9 px-4 bg-gradient-to-r from-[#155dfc] to-[#3b82f6] hover:from-[#114bc9] hover:to-[#2563eb] text-white font-extrabold text-sm rounded-lg shadow-lg shadow-blue-500/10 hover:shadow-blue-500/25 border-t border-white/20 transition-all">
            <Link to="/">무료 시작</Link>
          </Button>
        </div>
      </header>

      {/* 3. 영웅 배너 섹션 (Hero Section) */}
      <section className="relative pt-16 md:pt-24 pb-12 px-4 md:px-8 max-w-[1400px] mx-auto text-center flex flex-col items-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-[#155dfc] text-xs font-extrabold tracking-wide mb-6">
          웹 모의투자 플랫폼
        </div>

        <h1 className="text-[32px] md:text-[60px] font-black tracking-tight leading-[1.1] text-slate-900 max-w-[950px] mb-6 break-keep">
          투자에 필요한 모든 지표를 <br className="hidden md:inline" />
          프로그램 설치 없이{" "}
          <span className="bg-gradient-to-r from-[#155dfc] via-blue-500 to-sky-400 bg-clip-text text-transparent text-neon-glow">
            한 곳에서!
          </span>
        </h1>

        <p className="text-slate-500 text-base md:text-[18px] leading-relaxed max-w-[720px] font-semibold mb-10 break-keep">
          실시간 실제 호가, 고도화된 차트, 커뮤니티가 유기적으로 연동되는 싸피증권에서 <br />
          리스크 없이 생생한 모의투자를 경험해 보세요.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 mb-16 shrink-0">
          <Button asChild className="h-12 px-8 bg-gradient-to-r from-[#155dfc] to-[#3b82f6] hover:from-[#114bc9] hover:to-[#2563eb] text-white font-black text-[15px] rounded-xl shadow-2xl shadow-blue-500/20 hover:shadow-blue-500/35 border-t border-white/20 transition-all flex items-center gap-2 group">
            <Link to="/">
              로그인 없이 체험하기
            </Link>
          </Button>
        </div>

        {/* 🎆 3D 입체 기기 쇼케이스 (노트북 단독 중앙 배치) */}
        <div className="w-full max-w-[1100px] relative mt-8 perspective-[2000px] overflow-visible mb-16 flex flex-col items-center justify-center">
          <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 w-[70%] h-6 bg-gradient-to-r from-[#155dfc]/0 via-[#155dfc]/12 to-[#155dfc]/0 blur-md rounded-full scale-y-50 z-0" />

          {/* [1] 중앙 노트북 목업 (웅장하고 품격 있게 중앙에 대화면으로 단독 배치) */}
          <div className="w-[92%] max-w-[820px] aspect-[16/10] bg-white rounded-2xl border border-slate-200/80 shadow-[0_25px_60px_rgba(21,93,252,0.08)] animate-float-laptop origin-center flex flex-col overflow-hidden relative z-10">
            {/* 싸피증권 실제 메인 화면 캡처본 이미지 배치 (이미지 자체에 헤더가 포함되어 있어 중복 차단) */}
            <div className="flex-1 overflow-hidden relative bg-slate-50">
              <img src="/stock_main.png" alt="실제 메인 화면" className="w-full h-full object-fill select-none pointer-events-none" />
            </div>
            <div className="absolute -bottom-1 -left-2 w-[102%] h-[6px] bg-slate-300 rounded-b-xl border border-slate-200 border-t-0 shadow" />
          </div>
        </div>
      </section>

      {/* 📈 4. 소셜 프루프 카운터 (Dynamic Stats Counters) */}
      <section className="bg-white/60 backdrop-blur-md border-y border-slate-200/50 py-10 px-4 md:px-8">
        <div className="max-w-[1100px] mx-auto grid grid-cols-3 gap-4 text-center">
          <div className="flex flex-col">
            <span className="text-[20px] md:text-[36px] font-black text-[#155dfc] tracking-tight">
              {userCount.toLocaleString()}명+
            </span>
            <span className="text-[10px] md:text-xs text-slate-400 font-bold uppercase mt-1">누적 모의 투자자</span>
          </div>
          <div className="flex flex-col border-x border-slate-200/60">
            <span className="text-[20px] md:text-[36px] font-black text-[#155dfc] tracking-tight">
              {analysisCount.toLocaleString()}건+
            </span>
            <span className="text-[10px] md:text-xs text-slate-400 font-bold uppercase mt-1">누적 모의 거래 건수</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[20px] md:text-[36px] font-black text-[#fb2c36] tracking-tight">
              {activeUserCount.toLocaleString()}명
            </span>
            <span className="text-[10px] md:text-xs text-slate-400 font-bold uppercase mt-1">실시간 모의 트레이더</span>
          </div>
        </div>
      </section>

      {/* 🚀 5. 싸피증권 실제 거래 화면 쇼케이스 (Static Trading Suite Showcase with Tabs) */}
      <section id="trading-demo" className="py-20 px-4 md:px-8 max-w-[1400px] mx-auto">
        <div className="text-center max-w-[750px] mx-auto mb-8">
          <span className="text-xs font-black tracking-widest text-[#155dfc] uppercase">MOCK TRADING SUITE DISPLAY</span>
          <h2 className="text-[26px] md:text-[40px] font-black tracking-tight text-[#0f172a] mt-2 leading-tight">
            압도적인 직관성을 자랑하는 모의투자 화면
          </h2>
          <p className="text-slate-500 text-sm md:text-base leading-relaxed font-semibold mt-3 break-keep">
            실제 주식 시장 데이터와 실시간 랭킹 대시보드, 그리고 초보자도 쉽게 거래 감각을 익히는 싸피증권만의 모의투자 화면을 확인해 보세요.
          </p>
        </div>

        {/* 라이트 글래스모피즘 프리미엄 2단 탭 제어기 */}
        <div className="flex justify-center gap-3 mb-10 shrink-0">
          <button
            onClick={() => setShowcaseTab("main")}
            className={`px-6 py-3 text-xs font-extrabold rounded-xl border transition-all duration-300 cursor-pointer shadow-sm whitespace-nowrap ${showcaseTab === "main"
              ? "bg-[#155dfc] text-white border-[#155dfc] shadow-lg shadow-blue-500/15"
              : "bg-white text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700"
              }`}
          >
            실시간 주식 랭킹 (메인)
          </button>
          <button
            onClick={() => setShowcaseTab("detail")}
            className={`px-6 py-3 text-xs font-extrabold rounded-xl border transition-all duration-300 cursor-pointer shadow-sm whitespace-nowrap ${showcaseTab === "detail"
              ? "bg-[#155dfc] text-white border-[#155dfc] shadow-lg shadow-blue-500/15"
              : "bg-white text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700"
              }`}
          >
            상세 거래 화면 (삼성전자)
          </button>
        </div>

        {/* 탭 전환 상태에 따른 실제 싸피증권 고해상도 스크린샷 노출 */}
        <div className="w-full max-w-[1200px] mx-auto bg-white rounded-3xl border border-slate-200/80 shadow-2xl shadow-blue-500/5 p-2 flex flex-col font-sans text-left relative overflow-hidden bg-slate-50 transition-all hover:shadow-blue-500/10 hover:scale-[1.003] duration-500">
          {showcaseTab === "main" ? (
            <img
              src="/stock_main.png"
              alt="싸피증권 실제 메인 화면"
              className="w-full h-auto rounded-2xl select-none"
            />
          ) : (
            <img
              src="/stock_detail.png"
              alt="싸피증권 실제 거래 상세 화면"
              className="w-full h-auto rounded-2xl select-none"
            />
          )}
        </div>
      </section>

      {/* 📊 6. 100% 실제 한국거래소(KRX) 실시간 데이터 연동 시세 보드 (Real-Time Market Data Board) */}
      <section id="trending-themes" className="py-20 px-4 md:px-8 bg-white border-y border-slate-200/80 relative">
        <div className="max-w-[1400px] mx-auto">

          <div className="text-center max-w-[700px] mx-auto mb-16">
            <span className="text-xs font-black tracking-widest text-[#155dfc] uppercase">REAL-TIME MARKET DATA</span>
            <h2 className="text-[26px] md:text-[38px] font-black tracking-tight text-[#0f172a] mt-2 leading-tight break-keep">
              100% 실제 한국거래소(KRX) 실시간 데이터 시세 연동
            </h2>
            <p className="text-slate-500 text-sm md:text-base leading-relaxed font-semibold mt-3 break-keep">
              가짜 주가나 지연 데이터가 아닌, 100% 실제 한국거래소(KRX) 실시간 시세 위에서 실전과 똑같은 조건으로 생생한 모의투자를 즐기실 수 있습니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-[1000px] mx-auto">

            {/* 실시간 시세 데이터 리스트 */}
            <div className="bg-slate-50/50 border border-slate-200 rounded-3xl p-6 text-left shadow-sm">
              <span className="text-[10px] font-black text-slate-400 tracking-wider uppercase block mb-4">지연 없는 실제 국내 주식 시세 스트리밍</span>

              <div className="space-y-3">
                {REALTIME_STOCKS.map((stock) => (
                  <div key={stock.rank} className="bg-white border border-slate-100 p-3.5 rounded-2xl flex items-center justify-between shadow-sm hover:border-[#155dfc]/30 transition-all group">
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-lg bg-blue-50 text-[#155dfc] font-black text-[11px] flex items-center justify-center border border-blue-100 group-hover:scale-105 transition-all">
                        {stock.rank}
                      </span>
                      <span className="text-xs font-black text-slate-800">{stock.name}</span>
                    </div>
                    <div className="flex items-center gap-4 text-right">
                      <span className="text-xs font-bold text-slate-400">현재가: <strong className="text-slate-700 font-extrabold">{stock.price}</strong></span>
                      <span className="text-xs font-black text-[#fb2c36] bg-red-50 px-2 py-0.5 rounded">
                        {stock.change}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 실시간 금융 정보 가공 및 인사이트 카드 */}
            <div className="bg-[#f8faff] border border-blue-100 rounded-3xl p-6 text-left flex flex-col justify-between min-h-[380px]">
              <div>
                <div className="w-10 h-10 rounded-xl bg-blue-100 border border-blue-200 text-[#155dfc] flex items-center justify-center mb-6 shadow shadow-blue-500/5">
                  <Sparkles className="w-5 h-5 animate-pulse" />
                </div>
                <h3 className="text-[17px] font-black text-[#0f172a] tracking-tight mb-3 break-keep">실제 데이터 분석을 통한 스마트한 모의투자 학습</h3>
                <p className="text-slate-500 text-[13.5px] leading-relaxed font-semibold mb-6 break-keep">
                  한국거래소(KRX)의 실제 시세를 스트리밍하여 가공된 대규모 수급 데이터와 기관/외인의 동향 분석 지표를 보며, 단순한 감이 아닌 정밀한 금융 분석 기반의 모의투자를 훈련할 수 있습니다.
                </p>

                <div className="bg-white border border-blue-200/60 p-4 rounded-2xl flex flex-col gap-2">
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-black text-[#155dfc] uppercase tracking-wider">실시간 수급 강도 분석</span>
                    <span className="text-[9px] text-[#fb2c36] bg-red-50 font-black px-1.5 py-0.5 rounded">기관/외인 동반 순매수 우위</span>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden mt-1 relative">
                    <div className="absolute left-0 top-0 h-full bg-gradient-to-r from-[#155dfc] to-blue-400 rounded-full" style={{ width: "88%" }} />
                  </div>
                  <span className="text-[10px] text-slate-400 font-bold block mt-1">대규모 금융 빅데이터의 지연 없는 실시간 스트리밍 분석 기술</span>
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-blue-200/40 pt-4 mt-6">
                <span className="text-[10.5px] text-[#155dfc] font-black flex items-center gap-1">
                  <Volume2 className="w-3.5 h-3.5" />
                  실시간 주가 수급 처리 시스템 구동 중
                </span>
                <span className="text-[10px] text-slate-400 font-bold">1ms 이하 초고속 파이프라인</span>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* 📢 7. 서비스 특장점 및 반응형 쇼케이스 */}
      <section className="py-20 px-4 md:px-8 max-w-[1400px] mx-auto">
        <div className="text-center max-w-[700px] mx-auto mb-16">
          <span className="text-xs font-black tracking-widest text-[#155dfc] uppercase">WHY SSAFY STOCK</span>
          <h2 className="text-[26px] md:text-[38px] font-black tracking-tight text-[#0f172a] mt-2 leading-tight">
            단 하나의 기기도 막힘 없이
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

          <div className="bg-white border border-slate-200 rounded-3xl p-6 hover:border-[#155dfc]/30 hover:shadow-xl hover:shadow-[#155dfc]/5 transition-all flex flex-col justify-between min-h-[340px] group shadow-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 text-[#155dfc] flex items-center justify-center mb-6 group-hover:scale-105 transition-all">
                <Sparkles className="w-5 h-5" />
              </div>
              <h3 className="text-[16px] font-black text-[#0f172a] tracking-tight mb-3 break-keep">AI 모의 매매 시그널</h3>
              <p className="text-slate-500 text-[13.5px] leading-relaxed font-semibold break-keep">
                어지러운 기술 보조 지표들을 종합 분석하여 최적의 모의 매수, 매도 타점을 시각화된 시그널 게이지 형태로 안전하게 실습 제공합니다.
              </p>
            </div>

            <div className="mt-8 bg-slate-50 border border-slate-200 p-3 rounded-2xl flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-bold">실습 시그널</span>
              <span className="text-[10.5px] text-[#155dfc] bg-blue-50 font-black px-2 py-0.5 rounded">RSI 과매도 복귀</span>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-3xl p-6 hover:border-[#155dfc]/30 hover:shadow-xl hover:shadow-[#155dfc]/5 transition-all flex flex-col justify-between min-h-[340px] group shadow-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 text-[#155dfc] flex items-center justify-center mb-6 group-hover:scale-105 transition-all">
                <LineChart className="w-5 h-5" />
              </div>
              <h3 className="text-[16px] font-black text-[#0f172a] tracking-tight mb-3 break-keep">분석력을 높이는 프로급 차트</h3>
              <p className="text-slate-500 text-[13.5px] leading-relaxed font-semibold break-keep">
                클릭 단 한번으로 1분봉/일봉 전환과 보조지표를 제어하며 모의투자 분석 능력을 실제 프로 트레이더 수준으로 극대화시킵니다.
              </p>
            </div>

            <div className="mt-8 bg-slate-50 border border-slate-200 p-3 rounded-2xl flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-bold">차트 반응 속도</span>
              <span className="text-[10.5px] text-[#fb2c36] bg-red-50 font-black px-2 py-0.5 rounded">지연속도 0.05s</span>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-3xl p-6 hover:border-[#155dfc]/30 hover:shadow-xl hover:shadow-[#155dfc]/5 transition-all flex flex-col justify-between min-h-[340px] group shadow-sm">
            <div>
              <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 text-[#155dfc] flex items-center justify-center mb-6 group-hover:scale-105 transition-all">
                <Monitor className="w-5 h-5" />
              </div>
              <h3 className="text-[16px] font-black text-[#0f172a] tracking-tight mb-3 break-keep">언제 어디서나 모의투자</h3>
              <p className="text-slate-500 text-[13.5px] leading-relaxed font-semibold break-keep">
                SaaS 웹 아키텍처를 기반으로 PC, 태블릿, 모바일 등 어떤 기기에서 접속하든 나의 모의 거래 설정과 자산 포트폴리오를 완벽하게 연동합니다.
              </p>
            </div>

            <div className="mt-8 bg-slate-50 border border-slate-200 p-3 flex items-center justify-around rounded-2xl">
              <Monitor className="w-4 h-4 text-[#155dfc]" />
              <Tablet className="w-4 h-4 text-blue-400" />
              <Smartphone className="w-4 h-4 text-sky-400" />
            </div>
          </div>

        </div>
      </section>

      {/* 📢 8. 파이널 가입 유도 배너 */}
      <section className="py-20 px-4 md:px-8 max-w-[1400px] mx-auto text-center relative overflow-hidden">
        <div className="max-w-[1000px] mx-auto bg-gradient-to-r from-[#155dfc] to-[#3b82f6] rounded-3xl p-8 md:p-14 text-white flex flex-col items-center relative shadow-2xl shadow-blue-500/20">
          <div className="absolute -top-12 -left-12 w-48 h-48 rounded-full bg-white/5 blur-2xl" />
          <div className="absolute -bottom-12 -right-12 w-48 h-48 rounded-full bg-white/5 blur-2xl" />

          <h2 className="text-[24px] md:text-[38px] font-black tracking-tight leading-tight mb-4 break-keep">
            지금, 리스크 없는 스마트한 <br />
            차세대 모의투자를 시작해 보세요.
          </h2>
          <p className="text-white/80 text-xs md:text-sm max-w-[500px] font-semibold mb-8 break-keep">
            실제 시장 데이터 기반의 모의투자 시스템과 모든 고급 지표 분석이 100% 평생 무료로 오픈됩니다. 단 5초 만에 가입하고 투자 전략을 훈련하세요.
          </p>

          <Button asChild className="h-12 px-8 bg-white text-[#155dfc] hover:bg-slate-50 font-black text-[15px] rounded-xl shadow-lg border border-transparent transition-all">
            <Link to="/">
              무료 모의투자 시작하기
            </Link>
          </Button>
        </div>
      </section>

      {/* 9. 슬림하고 품격 있는 반투명 글래스모피즘 플로팅 Sticky 푸터 (B안) */}
      <footer className="fixed bottom-0 left-0 w-full z-40 bg-white/80 backdrop-blur-xl border-t border-slate-200/80 px-4 md:px-8 py-3 md:py-4 text-slate-500 text-xs text-left shadow-[0_-10px_30px_rgba(15,23,42,0.03)] transition-all">
        <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row justify-between items-center gap-4">

          <div className="flex items-center gap-3.5">
            <div className="flex items-center gap-0 shrink-0 font-sans">
              <img src="/ssafy_logo.png" alt="ssafy_logo" className="w-8 h-6.5" />
              <span className="font-extrabold text-[13px] text-[#0f172a] tracking-tight whitespace-nowrap">싸피증권</span>
            </div>
            <p className="hidden sm:block text-[10.5px] text-slate-400 font-semibold border-l border-slate-200 pl-3 leading-none whitespace-nowrap">
              실제 데이터 기반의 차세대 웹 모의투자 플랫폼
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-semibold font-sans text-[11px]">
            <span className="hover:text-[#155dfc] transition-colors cursor-pointer whitespace-nowrap">서비스 가치</span>
            <span className="hover:text-[#155dfc] transition-colors cursor-pointer whitespace-nowrap">이용약관</span>
            <span className="hover:text-[#155dfc] transition-colors cursor-pointer font-extrabold text-slate-700 whitespace-nowrap">개인정보 처리방침</span>
            <span className="hover:text-[#155dfc] transition-colors cursor-pointer whitespace-nowrap">투자 위험 고지</span>
            <span className="hover:text-[#155dfc] transition-colors cursor-pointer whitespace-nowrap">자주 묻는 질문</span>
            <span className="hover:text-[#155dfc] transition-colors cursor-pointer whitespace-nowrap">1:1 온라인 문의</span>
          </div>

        </div>
      </footer>

    </div>
  );
}
