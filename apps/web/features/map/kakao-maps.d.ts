// 카카오맵 JS SDK는 공식 타입 패키지를 쓰지 않고 스크립트 태그로 동적 로딩하므로,
// JejuMapPreview에서 실제로 쓰는 최소한의 형태만 전역 타입으로 선언해 `any` 사용을 줄인다.
export {};

declare global {
  interface Window {
    kakao?: {
      maps: {
        load: (callback: () => void) => void;
        LatLng: new (lat: number, lng: number) => unknown;
        Map: new (container: HTMLElement, options: { center: unknown; level: number }) => unknown;
        Marker: new (options: { position: unknown; map: unknown; title?: string }) => unknown;
        InfoWindow: new (options: { content: string }) => { open: (map: unknown, marker: unknown) => void };
        event: {
          addListener: (target: unknown, type: string, handler: () => void) => void;
        };
      };
    };
  }
}
