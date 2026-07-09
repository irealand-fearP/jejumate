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
        // 장소 검색(services) 라이브러리. libraries=services로 SDK를 로드해야 채워진다.
        services: {
          Places: new () => {
            // keywordSearch는 결과(x=경도, y=위도 문자열)와 상태 문자열을 콜백으로 준다.
            // options.rect("minLng,minLat,maxLng,maxLat")로 검색 범위를 사각형으로 한정할 수 있다.
            keywordSearch: (
              keyword: string,
              callback: (result: KakaoPlaceSearchItem[], status: string) => void,
              options?: KakaoPlaceSearchOptions,
            ) => void;
          };
          Status: { OK: string; ZERO_RESULT: string; ERROR: string };
        };
      };
    };
  }

  // keywordSearch 결과 한 건에서 좌표를 얻는 데 필요한 최소 필드만 선언한다.
  interface KakaoPlaceSearchItem {
    place_name: string;
    x: string; // 경도(lng)
    y: string; // 위도(lat)
  }

  // 실제로 쓰는 검색 옵션만 선언한다(rect로 제주 경계 안으로 한정).
  interface KakaoPlaceSearchOptions {
    rect?: string;
    size?: number;
  }
}
