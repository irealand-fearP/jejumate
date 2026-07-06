export type PostType = "party" | "info";
export type Source = "kakao" | "user_post";
export type Status = "active" | "closed";

export interface Post {
  id: string;
  source: Source;
  post_type: PostType;
  category: string;
  content: string;
  author_nickname: string;
  original_timestamp: string;
  chat_room_name: string | null;
  status: Status;
  capacity: number | null;
  deadline: string | null;
  created_at: string;
}

export interface Evidence {
  id: string;
  content: string;
  author_nickname: string;
  original_timestamp: string;
  source: Source;
  category: string;
  post_type: PostType;
}

export interface SearchResponse {
  answer: string;
  evidence: Evidence[];
}

export interface PartyPostCreateResponse {
  id: string;
  owner_secret: string;
  deadline: string;
}
