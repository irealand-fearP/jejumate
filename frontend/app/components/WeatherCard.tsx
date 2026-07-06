// 기획서 B등급 "날씨/이슈 피드 카드". 외부 API 없이 정적 mock 데이터로만 구성한다.
// 화면흐름.md에 배치 지침이 없어 피드 최상단 고정 카드로 둔다(카테고리 필터 영향 안 받음).
const MOCK_WEATHER = {
  condition: "맑음",
  icon: "☀️",
  high: 28,
  low: 22,
  note: "야외 활동하기 좋은 날씨예요. 자외선 지수는 높으니 선크림 챙기세요!",
};

export function WeatherCard() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-sky-200 bg-sky-50 p-4">
      <span className="text-3xl">{MOCK_WEATHER.icon}</span>
      <div className="flex-1">
        <p className="text-sm font-semibold text-sky-900">
          오늘 제주 날씨 · {MOCK_WEATHER.condition} {MOCK_WEATHER.high}° / {MOCK_WEATHER.low}°
        </p>
        <p className="mt-0.5 text-xs text-sky-700">{MOCK_WEATHER.note}</p>
      </div>
    </div>
  );
}
