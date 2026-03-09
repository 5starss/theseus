const { Kafka } = require('kafkajs');

// Kafka 설정
const kafka = new Kafka({
  clientId: 'mock-market-data-server',
  brokers: [process.env.KAFKA_BROKERS || 'localhost:9092']
});

const producer = kafka.producer();

// 10개 종목 리스트 및 기초가 설정
const STOCKS = [
  { ticker: '000660', name: 'SK하이닉스', price: 180000 },
  { ticker: '005380', name: '현대차', price: 250000 },
  { ticker: '005930', name: '삼성전자', price: 75000 },
  { ticker: '006400', name: '삼성SDI', price: 400000 },
  { ticker: '012330', name: '현대모비스', price: 220000 },
  { ticker: '034730', name: 'SK', price: 160000 },
  { ticker: '035420', name: 'NAVER', price: 180000 },
  { ticker: '051910', name: 'LG화학', price: 450000 },
  { ticker: '068270', name: '셀트리온', price: 180000 },
  { ticker: '207940', name: '삼성바이오로직스', price: 800000 }
];

// 현재가 관리 (Memory)
const stockState = STOCKS.map(s => ({ ...s }));

/**
 * 랜덤 시세 데이터 생성 (MarketDataEvent)
 * bestBid < price < bestAsk 형태 유지
 */
const generateMarketData = (stock) => {
  const spread = stock.price * 0.001; // 0.1% spread
  const bestBid = Math.floor(stock.price - (spread / 2));
  const bestAsk = Math.ceil(stock.price + (spread / 2));
  
  return {
    ticker: stock.ticker,
    bestBid: bestBid,
    bestAsk: bestAsk,
    timestamp: Date.now()
  };
};

/**
 * 랜덤 체결 데이터 생성 (TickDataEvent)
 */
const generateTickData = (stock) => {
  const volatility = stock.price * 0.0005 * (Math.random() - 0.5); // 아주 작은 변동성
  stock.price = Math.floor(stock.price + volatility);
  
  return {
    ticker: stock.ticker,
    price: stock.price,
    qty: Math.floor(Math.random() * 100) + 1, // 1~100주 랜덤
    timestamp: Date.now()
  };
};

const run = async () => {
  await producer.connect();
  console.log('✅ Kafka Producer Connected');

  // 1. 호가 데이터(MarketData) 발행 루프 - 500ms 주기
  setInterval(async () => {
    try {
      const messages = stockState.map(stock => ({
        value: JSON.stringify(generateMarketData(stock))
      }));

      await producer.send({
        topic: 'market-data-events',
        messages
      });
      // console.log('📤 Published MarketData to market-data-events');
    } catch (err) {
      console.error('❌ Failed to publish market data:', err);
    }
  }, 500);

  // 2. 체결 데이터(TickData) 발행 루프 - 1000ms 주기
  setInterval(async () => {
    try {
      // 10개 중 랜덤으로 3~5개 종목만 체결 발생 시뮬레이션
      const batch = stockState
        .filter(() => Math.random() > 0.6)
        .map(stock => ({
          value: JSON.stringify(generateTickData(stock))
        }));

      if (batch.length > 0) {
        await producer.send({
          topic: 'market-trade-events',
          messages: batch
        });
        console.log(`📤 Published ${batch.length} ticks to market-trade-events`);
      }
    } catch (err) {
      console.error('❌ Failed to publish tick data:', err);
    }
  }, 1000);
};

run().catch(console.error);
