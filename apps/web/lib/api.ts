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
};

export type HomePolicy = {
  id: string;
  title: string;
  summary: string;
  region: string;
  field: string;
  status: string;
  application_end_date: string;
  d_day: number;
  official_url: string;
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
  policies: HomePolicy[];
};

export type MeetingsData = {
  filters: string[];
  meetings: HomeMeeting[];
  privacy_note: string;
};

export type PoliciesData = {
  policies: HomePolicy[];
  last_synced_at: string;
  source_note: string;
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

// 승인/거절처럼 바디 없이 query string만 쓰는 POST용. 403/400/409 등의 detail 메시지를
// 그대로 던져서(정원이 찼어요 등) 화면에 보여줄 수 있게 한다.
async function postApiQuery<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST" });

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

export async function getPoliciesData(): Promise<PoliciesData> {
  return getApi<PoliciesData>("/api/policies");
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
