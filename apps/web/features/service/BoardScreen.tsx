"use client";

import { useMemo, useState } from "react";
import { Check, ChevronRight, Flag, MessageCircle, Plus, Search, Trash2, X } from "lucide-react";
import { MobileShell } from "@/features/common/MobileShell";
import { Pagination } from "@/features/common/Pagination";
import { usePagination } from "@/features/common/usePagination";
import {
  createBoardComment,
  createBoardPost,
  createNickname,
  deleteBoardPost,
  getBoardPost,
  reportBoardPost,
  type BoardData,
  type BoardPost,
  type NicknameProfile,
} from "@/lib/api";
import styles from "./ServicePages.module.css";

const PROFILE_STORAGE_KEY = "jejumate.localProfile";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

function buildLocalProfile(profile: NicknameProfile): LocalProfile {
  return {
    profileId: profile.profile_id,
    nickname: profile.nickname,
    anonymousId: profile.anonymous_id,
  };
}

function readProfile(): LocalProfile | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as LocalProfile;
    return parsed.nickname && parsed.anonymousId ? parsed : null;
  } catch {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    return null;
  }
}

function formatRelativeTime(value: string): string {
  const diffMs = Date.now() - new Date(value).getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diffMs < minute) return "방금 전";
  if (diffMs < hour) return `${Math.floor(diffMs / minute)}분 전`;
  if (diffMs < day) return `${Math.floor(diffMs / hour)}시간 전`;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

export function BoardScreen({ data }: { data: BoardData }) {
  const [boardData, setBoardData] = useState(data);
  const filters = useMemo(() => ["전체", ...boardData.categories], [boardData.categories]);
  const [activeFilter, setActiveFilter] = useState(filters[0] ?? "전체");
  const [selectedPost, setSelectedPost] = useState<BoardPost | null>(null);
  const [showWriteSheet, setShowWriteSheet] = useState(false);
  const [profile, setProfile] = useState<LocalProfile | null>(() => readProfile());
  const [category, setCategory] = useState(data.categories[0] ?? "질문게시판");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [nickname, setNickname] = useState(() => readProfile()?.nickname ?? "");
  const [commentBody, setCommentBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [searchKeyword, setSearchKeyword] = useState("");

  const posts = useMemo(() => {
    // 카테고리 칩을 먼저 적용하고, 검색어를 AND로 겹쳐 더 좁힌다.
    const filtered =
      activeFilter === "전체" ? boardData.posts : boardData.posts.filter((post) => post.category === activeFilter);

    // 글 목록을 이미 통으로 받아왔으므로 검색은 프론트 필터링으로 충분하다(새 API 불필요).
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) return filtered;

    return filtered.filter((post) =>
      [post.title, post.body, post.author_nickname].some((field) => field?.toLowerCase().includes(keyword)),
    );
  }, [activeFilter, boardData.posts, searchKeyword]);

  // 카테고리 필터나 검색어가 바뀌면 1페이지로 되돌린다.
  const {
    page,
    totalPages,
    pageItems: pagedPosts,
    goToPage,
    listTopRef,
  } = usePagination(posts, `${activeFilter}|${searchKeyword.trim()}`);

  function saveProfileLocally(nextProfile: LocalProfile) {
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
    setProfile(nextProfile);
    setNickname(nextProfile.nickname);
  }

  async function ensureProfile(): Promise<LocalProfile> {
    if (profile) return profile;
    const created = buildLocalProfile(await createNickname(nickname.trim()));
    saveProfileLocally(created);
    return created;
  }

  async function openPost(post: BoardPost) {
    setNotice(null);
    setSelectedPost(post);
    try {
      setSelectedPost(await getBoardPost(post.id, profile?.anonymousId));
    } catch {
      setNotice("게시글을 불러오지 못했습니다.");
    }
  }

  function closeWriteSheet() {
    setShowWriteSheet(false);
    setTitle("");
    setBody("");
    setNotice(null);
  }

  async function submitPost() {
    if (title.trim().length < 2 || body.trim().length < 2 || nickname.trim().length < 2) return;

    setBusy(true);
    setNotice(null);
    try {
      const currentProfile = await ensureProfile();
      const created = await createBoardPost({
        category,
        title: title.trim(),
        body: body.trim(),
        author_nickname: currentProfile.nickname,
        anonymous_id: currentProfile.anonymousId,
      });
      setBoardData((current) => ({ ...current, posts: [created, ...current.posts] }));
      setActiveFilter("전체");
      closeWriteSheet();
      setSelectedPost(created);
    } catch {
      setNotice("글을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  async function submitComment() {
    if (!selectedPost || commentBody.trim().length < 1 || nickname.trim().length < 2) return;

    setBusy(true);
    setNotice(null);
    try {
      const currentProfile = await ensureProfile();
      const updated = await createBoardComment(selectedPost.id, {
        body: commentBody.trim(),
        author_nickname: currentProfile.nickname,
        anonymous_id: currentProfile.anonymousId,
      });
      setSelectedPost(updated);
      setCommentBody("");
      setBoardData((current) => ({
        ...current,
        posts: current.posts.map((post) =>
          post.id === updated.id ? { ...post, comment_count: updated.comment_count } : post
        ),
      }));
    } catch {
      setNotice("댓글을 저장하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function removeSelectedPost() {
    if (!selectedPost || !profile?.anonymousId) return;

    setBusy(true);
    setNotice(null);
    try {
      await deleteBoardPost(selectedPost.id, profile.anonymousId);
      setBoardData((current) => ({
        ...current,
        posts: current.posts.filter((post) => post.id !== selectedPost.id),
      }));
      setSelectedPost(null);
    } catch {
      setNotice("본인 글만 삭제할 수 있습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function reportSelectedPost() {
    if (!selectedPost) return;

    setBusy(true);
    setNotice(null);
    try {
      await reportBoardPost(selectedPost.id, {
        reason: "부적절한 생활게시판 글",
        anonymous_id: profile?.anonymousId,
      });
      setNotice("신고가 접수되었습니다.");
    } catch {
      setNotice("신고를 접수하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <MobileShell active="board" title="생활게시판" subtitle="이웃과 가볍게 묻고 나눠요">
      <div className={styles.notice}>{boardData.notice}</div>
      <div className={styles.boardActionRow}>
        <div className={styles.toolbar}>
          {filters.map((filter) => (
            <button
              className={`${styles.chip} ${activeFilter === filter ? styles.chipActive : ""}`}
              key={filter}
              onClick={() => setActiveFilter(filter)}
              type="button"
            >
              {filter}
            </button>
          ))}
        </div>
        <button className={styles.boardWriteButton} onClick={() => setShowWriteSheet(true)} type="button">
          <Plus size={16} />
          글쓰기
        </button>
      </div>

      <div className={styles.meetingSearch}>
        <Search size={16} aria-hidden="true" />
        <input
          aria-label="게시글 검색"
          onChange={(event) => setSearchKeyword(event.target.value)}
          placeholder="글 제목·내용·닉네임 검색"
          type="search"
          value={searchKeyword}
        />
      </div>

      <div ref={listTopRef} />

      <section className={styles.boardList}>
        {posts.length ? (
          pagedPosts.map((post) => (
            <button className={styles.boardCard} key={post.id} onClick={() => openPost(post)} type="button">
              <span className={styles.boardCategoryTag}>{post.category}</span>
              {post.source === "kakao_chat" ? (
                <span className={styles.externalBadge}>오픈채팅에서 온 글</span>
              ) : null}
              <h2>{post.title}</h2>
              <p>{post.body}</p>
              <span className={styles.boardMeta}>
                {post.author_nickname} · {formatRelativeTime(post.created_at)} · 댓글 {post.comment_count}
              </span>
              <ChevronRight className={styles.boardChevron} size={18} />
            </button>
          ))
        ) : (
          <div className={styles.boardEmpty}>
            {searchKeyword.trim() ? (
              <>
                <b>검색 결과가 없어요</b>
                <span>{`'${searchKeyword.trim()}'와 맞는 글을 찾지 못했어요.`}</span>
              </>
            ) : (
              <>
                <b>아직 글이 없어요</b>
                <span>첫 질문이나 나눔 글을 남겨보세요.</span>
              </>
            )}
          </div>
        )}
      </section>

      <Pagination onChange={goToPage} page={page} totalPages={totalPages} />

      {selectedPost ? (
        <div className={styles.sheetBackdrop} onClick={() => setSelectedPost(null)}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <div className={styles.sheetGrip} />
            <button className={styles.sheetClose} onClick={() => setSelectedPost(null)} type="button" aria-label="닫기">
              <X size={18} />
            </button>
            <div className={styles.sheetHero}>
              <span>{selectedPost.category}</span>
              {selectedPost.source === "kakao_chat" ? (
                <span className={styles.externalBadge}>오픈채팅에서 온 글</span>
              ) : null}
              <h2>{selectedPost.title}</h2>
              <p>
                {selectedPost.author_nickname} · {formatRelativeTime(selectedPost.created_at)}
              </p>
            </div>
            <article className={styles.boardDetail}>{selectedPost.body}</article>
            <div className={styles.boardDetailActions}>
              <button disabled={busy} onClick={reportSelectedPost} type="button">
                <Flag size={15} />
                신고
              </button>
              {selectedPost.can_delete ? (
                <button className={styles.dangerButton} disabled={busy} onClick={removeSelectedPost} type="button">
                  <Trash2 size={15} />
                  삭제
                </button>
              ) : null}
            </div>
            <section className={styles.commentSection}>
              <h3>
                <MessageCircle size={16} />
                댓글 {selectedPost.comment_count}
              </h3>
              <div className={styles.commentList}>
                {selectedPost.comments.length ? (
                  selectedPost.comments.map((comment) => (
                    <article className={styles.commentItem} key={comment.id}>
                      <b>{comment.author_nickname}</b>
                      <span>{comment.body}</span>
                      <small>{formatRelativeTime(comment.created_at)}</small>
                    </article>
                  ))
                ) : (
                  <p className={styles.commentEmpty}>아직 댓글이 없습니다.</p>
                )}
              </div>
              <div className={styles.commentForm}>
                <input
                  className={styles.input}
                  maxLength={20}
                  onChange={(event) => setNickname(event.target.value)}
                  placeholder="닉네임"
                  value={nickname}
                />
                <textarea
                  className={styles.textarea}
                  maxLength={300}
                  onChange={(event) => setCommentBody(event.target.value)}
                  placeholder="댓글을 남겨보세요."
                  value={commentBody}
                />
                <button
                  className={styles.primaryButton}
                  disabled={busy || nickname.trim().length < 2 || commentBody.trim().length < 1}
                  onClick={submitComment}
                  type="button"
                >
                  댓글 등록
                </button>
              </div>
            </section>
            {notice ? <div className={styles.result}>{notice}</div> : null}
          </section>
        </div>
      ) : null}

      {showWriteSheet ? (
        <div className={styles.sheetBackdrop} onClick={closeWriteSheet}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <div className={styles.sheetGrip} />
            <button className={styles.sheetClose} onClick={closeWriteSheet} type="button" aria-label="닫기">
              <X size={18} />
            </button>
            <div className={styles.sheetHero}>
              <span>생활게시판</span>
              <h2>새 글 쓰기</h2>
              <p>닉네임, 제목, 본문만 공개됩니다.</p>
            </div>
            <div className={styles.form}>
              <label className={styles.label} htmlFor="board-category">
                게시판
              </label>
              <select
                className={styles.input}
                id="board-category"
                onChange={(event) => setCategory(event.target.value)}
                value={category}
              >
                {boardData.categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <label className={styles.label} htmlFor="board-nickname">
                닉네임
              </label>
              <input
                className={styles.input}
                id="board-nickname"
                maxLength={20}
                onChange={(event) => setNickname(event.target.value)}
                value={nickname}
              />
              <label className={styles.label} htmlFor="board-title">
                제목
              </label>
              <input
                className={styles.input}
                id="board-title"
                maxLength={80}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="예: 함덕 근처 빨래방 추천해주세요"
                value={title}
              />
              <label className={styles.label} htmlFor="board-body">
                내용
              </label>
              <textarea
                className={styles.textarea}
                id="board-body"
                maxLength={500}
                onChange={(event) => setBody(event.target.value)}
                placeholder="연락처나 실명 대신 공개 가능한 정보만 적어주세요."
                value={body}
              />
              <button
                className={styles.primaryButton}
                disabled={busy || title.trim().length < 2 || body.trim().length < 2 || nickname.trim().length < 2}
                onClick={submitPost}
                type="button"
              >
                <Check size={16} />
                {busy ? "저장 중" : "등록하기"}
              </button>
            </div>
            {notice ? <div className={styles.result}>{notice}</div> : null}
          </section>
        </div>
      ) : null}
    </MobileShell>
  );
}
