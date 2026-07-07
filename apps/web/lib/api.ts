const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ApiResponse<T> = {
  request_id: string;
  data: T;
};

export type HomeMeeting = {
  id: string;
  category: string;
  title: string;
  starts_at: string;
  ends_at: string;
  place_label: string;
  host: {
    profile_id: string;
    nickname: string;
    badge: string | null;
  };
  capacity: number;
  approved_count: number;
  status: string;
  cta: {
    label: string;
    enabled: boolean;
    requires_auth: boolean;
  };
  // 인기/NEW 배지는 백엔드가 단일 계산해서 내려준다(프론트는 그대로 렌더만).
  is_popular: boolean;
  is_new: boolean;
};

export type HomeData = {
  profile_chip: {
    label: string;
    is_set: boolean;
  };
  privacy_chip: {
    label: string;
    is_verified: boolean;
  };
  meeting_summary: {
    open_count: number;
  };
  meeting_filters: string[];
  meetings: HomeMeeting[];
  activity_summary: {
    active_people_count: number;
    thumbnail_keys: string[];
  };
  rag_strip: {
    title: string;
    subtitle: string;
    suggestions: string[];
  };
};

export type MeetingsData = {
  filters: string[];
  meetings: HomeMeeting[];
  privacy_note: string;
};

export type BoardPost = {
  id: string;
  category: string;
  title: string;
  body: string;
  author_nickname: string;
  created_at: string;
  comment_count: number;
  can_delete: boolean;
  comments: BoardComment[];
};

export type BoardComment = {
  id: string;
  post_id: string;
  body: string;
  author_nickname: string;
  created_at: string;
};

export type BoardPostCreatePayload = {
  category: string;
  title: string;
  body: string;
  author_nickname: string;
  anonymous_id?: string;
};

export type BoardCommentCreatePayload = {
  body: string;
  author_nickname: string;
  anonymous_id?: string;
};

export type BoardReportPayload = {
  reason: string;
  anonymous_id?: string;
};

export type BoardDeleteResult = {
  post_id: string;
  status: string;
};

export type BoardReportResult = {
  target_type: string;
  target_id: string;
  status: string;
};

export type BoardData = {
  categories: string[];
  posts: BoardPost[];
  notice: string;
};

export type ProfilePreviewData = {
  public_fields: string[];
  hidden_fields: string[];
  default_interests: string[];
  safety_notes: string[];
};

export type NicknameProfile = {
  profile_id: string;
  nickname: string;
  anonymous_id: string;
  public_note: string;
  persisted?: boolean;
};

export type MeetingApplicationResult = {
  application_id: string;
  meeting_id: string;
  status: string;
  public_alias: string;
  privacy_note: string;
  next_step: string;
  persisted?: boolean;
};

export type MeetingCreateResult = {
  meeting_id: string;
  owner_secret: string;
  starts_at: string;
  ends_at: string;
  persisted?: boolean;
};

export type MeetingStatus = {
  capacity: number;
  approved_count: number;
  is_closed: boolean;
};

export type MeetingApplicationItem = {
  application_id: string | null;
  nickname: string;
  message: string | null;
  status: string | null;
};

export type MeetingApplicationListResult = {
  authorized: boolean;
  applications: MeetingApplicationItem[];
};

export type MeetingApplicationDecisionResult = {
  application_id: string;
  meeting_id: string;
  status: string;
};

export type ApplicationDeleteResult = {
  application_id: string;
  meeting_id: string;
  status: string;
};

export type ApplicantNotification = {
  application_id: string;
  meeting_id: string;
  meeting_title: string;
  starts_at: string;
  place_label: string;
  host_nickname: string;
  status: string;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
};

export type ApplicantNotificationsResult = {
  notifications: ApplicantNotification[];
};

export type ChatMessage = {
  id: string;
  meeting_id: string;
  sender_nickname: string;
  content: string;
  created_at: string;
};

export type ChatMessagesResult = {
  meeting_id: string;
  messages: ChatMessage[];
  notice: string;
  persisted?: boolean;
};

export type RagAnswer = {
  answer: string;
  sources: Array<{
    title: string;
    url: string;
    source_type: string;
  }>;
  safety_note: string;
  suggestions: string[];
  query_log_id?: string | null;
  persisted?: boolean;
};

async function postApi<TResponse, TPayload>(path: string, payload: TPayload): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  const body = (await response.json()) as ApiResponse<TResponse>;
  return body.data;
}

async function getApi<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  const body = (await response.json()) as ApiResponse<TResponse>;
  return body.data;
}

// 승인/거절/삭제처럼 바디 없이 query string만 쓰는 요청용. 403/400/409 등의 detail
// 메시지를 그대로 던져서(정원이 찼어요 등) 화면에 보여줄 수 있게 한다.
async function postApiQuery<TResponse>(path: string, method: "POST" | "DELETE" = "POST"): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      detail = errorBody?.detail;
    } catch {
      // 에러 바디가 JSON이 아니면 무시하고 기본 메시지 사용
    }
    throw new Error(detail ?? `API request failed: ${response.status}`);
  }

  const body = (await response.json()) as ApiResponse<TResponse>;
  return body.data;
}

export async function getHomeData(): Promise<HomeData> {
  return getApi<HomeData>("/api/home");
}

export async function getMeetingsData(): Promise<MeetingsData> {
  return getApi<MeetingsData>("/api/meetings");
}

export type MeetingCreatePayload = {
  category: string;
  title: string;
  description?: string;
  place_label: string;
  capacity: number;
  duration_minutes: number;
  nickname: string;
  anonymous_id?: string;
};

export async function createMeeting(payload: MeetingCreatePayload): Promise<MeetingCreateResult> {
  return postApi<MeetingCreateResult, MeetingCreatePayload>("/api/meetings", payload);
}

export async function getMeetingStatus(meetingId: string): Promise<MeetingStatus> {
  return getApi<MeetingStatus>(`/api/meetings/${meetingId}/status`);
}

export async function getMeetingApplications(
  meetingId: string,
  ownerSecret?: string
): Promise<MeetingApplicationListResult> {
  const query = ownerSecret ? `?owner_secret=${encodeURIComponent(ownerSecret)}` : "";
  return getApi<MeetingApplicationListResult>(`/api/meetings/${meetingId}/applications${query}`);
}

export async function approveMeetingApplication(
  meetingId: string,
  applicationId: string,
  ownerSecret: string
): Promise<MeetingApplicationDecisionResult> {
  return postApiQuery<MeetingApplicationDecisionResult>(
    `/api/meetings/${meetingId}/applications/${applicationId}/approve?owner_secret=${encodeURIComponent(ownerSecret)}`
  );
}

export async function rejectMeetingApplication(
  meetingId: string,
  applicationId: string,
  ownerSecret: string
): Promise<MeetingApplicationDecisionResult> {
  return postApiQuery<MeetingApplicationDecisionResult>(
    `/api/meetings/${meetingId}/applications/${applicationId}/reject?owner_secret=${encodeURIComponent(ownerSecret)}`
  );
}

// 신청자 알림(내 신청 상태 확인). 호스트 액션이 아니라 신청자 본인 조회라 anonymous_id로 스코프한다.
export async function getMyApplicationNotifications(anonymousId: string): Promise<ApplicantNotificationsResult> {
  return getApi<ApplicantNotificationsResult>(
    `/api/meetings/applications/notifications?anonymous_id=${encodeURIComponent(anonymousId)}`
  );
}

// 신청 삭제(본인 취소). 승인/거절과 달리 owner_secret이 아니라 anonymous_id로 본인 확인한다.
export async function deleteMyApplication(
  meetingId: string,
  applicationId: string,
  anonymousId: string
): Promise<ApplicationDeleteResult> {
  return postApiQuery<ApplicationDeleteResult>(
    `/api/meetings/${meetingId}/applications/${applicationId}?anonymous_id=${encodeURIComponent(anonymousId)}`,
    "DELETE"
  );
}

export async function getBoardData(): Promise<BoardData> {
  return getApi<BoardData>("/api/board");
}

export async function getBoardPost(postId: string, anonymousId?: string): Promise<BoardPost> {
  const query = anonymousId ? `?anonymous_id=${encodeURIComponent(anonymousId)}` : "";
  return getApi<BoardPost>(`/api/board/posts/${postId}${query}`);
}

export async function createBoardPost(payload: BoardPostCreatePayload): Promise<BoardPost> {
  return postApi<BoardPost, BoardPostCreatePayload>("/api/board/posts", payload);
}

export async function deleteBoardPost(postId: string, anonymousId: string): Promise<BoardDeleteResult> {
  return postApiQuery<BoardDeleteResult>(
    `/api/board/posts/${postId}?anonymous_id=${encodeURIComponent(anonymousId)}`,
    "DELETE"
  );
}

export async function createBoardComment(postId: string, payload: BoardCommentCreatePayload): Promise<BoardPost> {
  return postApi<BoardPost, BoardCommentCreatePayload>(`/api/board/posts/${postId}/comments`, payload);
}

export async function reportBoardPost(postId: string, payload: BoardReportPayload): Promise<BoardReportResult> {
  return postApi<BoardReportResult, BoardReportPayload>(`/api/board/posts/${postId}/reports`, payload);
}

export async function getProfilePreviewData(): Promise<ProfilePreviewData> {
  return getApi<ProfilePreviewData>("/api/profile/preview");
}

export async function createNickname(nickname: string, anonymousId?: string): Promise<NicknameProfile> {
  return postApi<NicknameProfile, { nickname: string; anonymous_id?: string }>("/api/onboarding/nickname", {
    nickname,
    anonymous_id: anonymousId,
  });
}

export async function submitMeetingApplication(
  meetingId: string,
  payload: { nickname: string; message?: string; anonymous_id?: string }
): Promise<MeetingApplicationResult> {
  return postApi<MeetingApplicationResult, { nickname: string; message?: string; anonymous_id?: string }>(
    `/api/meetings/${meetingId}/applications`,
    payload
  );
}

export async function getMeetingChatMessages(meetingId: string): Promise<ChatMessagesResult> {
  return getApi<ChatMessagesResult>(`/api/meetings/${meetingId}/chat/messages`);
}

export async function sendMeetingChatMessage(
  meetingId: string,
  payload: { nickname: string; content: string; anonymous_id?: string }
): Promise<ChatMessagesResult> {
  return postApi<ChatMessagesResult, { nickname: string; content: string; anonymous_id?: string }>(
    `/api/meetings/${meetingId}/chat/messages`,
    payload
  );
}

export async function askRag(question: string, anonymousId?: string): Promise<RagAnswer> {
  return postApi<RagAnswer, { question: string; anonymous_id?: string }>("/api/rag/ask", {
    question,
    anonymous_id: anonymousId,
  });
}
