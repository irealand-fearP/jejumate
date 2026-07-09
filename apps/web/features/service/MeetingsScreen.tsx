"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Bell,
  CalendarClock,
  Car,
  Check,
  CheckCircle2,
  Coffee,
  Copy,
  Dumbbell,
  KeyRound,
  Laptop,
  LockKeyhole,
  MapPin,
  Plus,
  Search,
  Trash2,
  Utensils,
  UsersRound,
  X,
} from "lucide-react";
import {
  approveMeetingApplication,
  createMeeting,
  createNickname,
  deleteMyApplication,
  getMeetingApplications,
  getMeetingsData,
  getMeetingStatus,
  getMyApplicationNotifications,
  rejectMeetingApplication,
  submitMeetingApplication,
  type ApplicantNotification,
  type HomeMeeting,
  type MeetingApplicationItem,
  type MeetingsData,
  type MeetingStatus,
} from "@/lib/api";
import { markNotificationsSeenNow } from "@/lib/applicantNotifications";
import { buildApplicationStatusMap, describeApplicationStatus } from "@/lib/applicationStatus";
import { formatCapacityStatus } from "@/lib/format";
import { CATEGORY_TO_FILTER, FILTER_TO_CATEGORIES } from "@/lib/meetingCategories";
import { getOwnerSecret, saveOwnerSecret } from "@/lib/ownerSecret";
import { ApplicantNotificationBanner } from "@/features/common/ApplicantNotificationBanner";
import { CenterModal } from "@/features/common/CenterModal";
import { ChatSheet } from "@/features/common/ChatSheet";
import { HostPendingBanner } from "@/features/common/HostPendingBanner";
import { MobileShell } from "@/features/common/MobileShell";
import { Pagination } from "@/features/common/Pagination";
import { usePagination } from "@/features/common/usePagination";
import { PlaceMapSection } from "@/features/map/PlaceMapSection";
import styles from "./ServicePages.module.css";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

const PROFILE_STORAGE_KEY = "jejumate.localProfile";
const STATUS_POLL_INTERVAL_MS = 8000;
const MEETINGS_POLL_INTERVAL_MS = 15000;

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function readProfile(): LocalProfile | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as LocalProfile;
  } catch {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    return null;
  }
}

const categoryIcon: Record<string, typeof UsersRound> = {
  meal: Utensils,
  work: Laptop,
  move: Car,
  coffee: Coffee,
  run: Dumbbell,
};

// 모임 생성 폼의 카테고리 칩. 화면 필터(전체/이동/밥친구/러닝/기타/오픈채팅)와 맞춰
// 사용자가 직접 만드는 모임엔 없는 '전체'·'오픈채팅'은 제외했다. '기타' 선택 시
// 저장값은 새 category 값 "other"를 쓴다(백엔드에 enum 제약이 없어 추가해도 안전하고,
// 기존 work/coffee와 구분해두면 나중에 집계할 때 헷갈리지 않는다) — meetingCategories.ts의
// FILTER_TO_CATEGORIES.기타에도 포함되어 있어 필터링과도 어긋나지 않는다.
const CREATE_CATEGORIES = [
  { value: "move", label: "이동" },
  { value: "meal", label: "밥친구" },
  { value: "run", label: "러닝" },
  { value: "other", label: "기타" },
];

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

// <input type="datetime-local"> 기본값 포맷(오프셋 없음, 브라우저 로컬 시각 그대로).
function toDatetimeLocalValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function getMeetingIcon(category: string) {
  return categoryIcon[category] ?? UsersRound;
}

export function MeetingsScreen({ data }: { data: MeetingsData }) {
  const searchParams = useSearchParams();
  const [meetings, setMeetings] = useState(data.meetings);
  const [activeFilter, setActiveFilter] = useState(() => {
    if (searchParams.get("source") === "kakao_chat" && data.filters.includes("오픈채팅")) return "오픈채팅";
    const categoryParam = searchParams.get("category");
    const filterFromCategory = categoryParam ? CATEGORY_TO_FILTER[categoryParam] : undefined;
    if (filterFromCategory && data.filters.includes(filterFromCategory)) return filterFromCategory;
    return data.filters[0] ?? "전체";
  });
  const [searchKeyword, setSearchKeyword] = useState("");
  // 신청 성공 안내(중앙 모달) 본문. null이면 모달을 띄우지 않는다.
  const [applicationDone, setApplicationDone] = useState<string | null>(null);
  const [selected, setSelected] = useState<HomeMeeting | null>(null);
  const [profile, setProfile] = useState<LocalProfile | null>(() => readProfile());
  const [nickname, setNickname] = useState(profile?.nickname ?? "");
  const [message, setMessage] = useState("");
  const [privacyChecked, setPrivacyChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  // 모임 등록(4자리 관리코드 발급, jejumate/backend POST /posts/party와 동일 패턴).
  const [showCreateSheet, setShowCreateSheet] = useState(false);
  const [createCategory, setCreateCategory] = useState(CREATE_CATEGORIES[0].value);
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createPlace, setCreatePlace] = useState("");
  const [createCapacity, setCreateCapacity] = useState(2);
  const [createStartsAt, setCreateStartsAt] = useState(() => toDatetimeLocalValue(new Date()));
  const [createEndsAt, setCreateEndsAt] = useState(() => toDatetimeLocalValue(new Date(Date.now() + 60 * 60 * 1000)));
  // 호스트 닉네임은 내정보(로컬 프로필)를 그대로 쓴다. 아직 닉네임이 없는 사용자를 위한
  // 안내용 인라인 입력(제출 시 쓰는 값이 아니라 프로필을 새로 만들 때만 사용).
  const [createNicknameDraft, setCreateNicknameDraft] = useState("");
  const [createNicknameSaving, setCreateNicknameSaving] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createResult, setCreateResult] = useState<{ meetingId: string; ownerSecret: string } | null>(null);
  const [createCopied, setCreateCopied] = useState(false);

  // 내가 만든 모임 관리(신청 목록 조회 + 승인/거절, jejumate/backend approve/reject와 동일 규칙).
  const [ownedMeetingIds, setOwnedMeetingIds] = useState<Set<string>>(new Set());
  const [manageMeeting, setManageMeeting] = useState<HomeMeeting | null>(null);
  const [manageStatus, setManageStatus] = useState<MeetingStatus | null>(null);
  const [manageOwnerCode, setManageOwnerCode] = useState("");
  const [manageApplications, setManageApplications] = useState<MeetingApplicationItem[] | null>(null);
  const [manageAuthorized, setManageAuthorized] = useState(false);
  const [manageCodeChecked, setManageCodeChecked] = useState(false);
  const [manageDecisionError, setManageDecisionError] = useState<string | null>(null);

  // 내 신청 알림(코덱스 원본 신규 기능 이식). 호스트 액션이 아니라 신청자 본인 조회라
  // owner_secret이 아니라 anonymous_id로 스코프한다.
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<ApplicantNotification[] | null>(null);
  const [notificationsError, setNotificationsError] = useState<string | null>(null);
  const [notificationBusyId, setNotificationBusyId] = useState<string | null>(null);

  // 모임 채팅(ChatSheet 공용 컴포넌트). 접근 조건은 HomeScreen의 hasChatAccess와 동일하다
  // — 호스트(ownedMeetingIds) 또는 승인된 신청자(approvedApplications).
  // 승인된 신청의 meeting_id -> application_id 매핑. 채팅 접근 권한 판단은 물론
  // 탈퇴 버튼에 필요한 application_id 조회에도 이 맵을 그대로 쓴다.
  const [approvedApplications, setApprovedApplications] = useState<Map<string, string>>(new Map());
  // 모임 카드 신청 버튼 배지용 전체 신청 상태(pending/approved/rejected) 맵.
  const [applicationStatusByMeetingId, setApplicationStatusByMeetingId] = useState<Map<string, string>>(new Map());
  const [chatMeeting, setChatMeeting] = useState<HomeMeeting | null>(null);

  useEffect(() => {
    const owned = new Set<string>();
    for (const meeting of meetings) {
      if (getOwnerSecret(meeting.id)) owned.add(meeting.id);
    }
    setOwnedMeetingIds(owned);
  }, [meetings]);

  // 채팅 접근 권한(승인된 신청자) 판단용. 호스트 여부는 ownedMeetingIds로 별도 판단한다
  // (HomeScreen.tsx의 동일 로직과 맞춰뒀다).
  useEffect(() => {
    if (!profile?.anonymousId) return;
    getMyApplicationNotifications(profile.anonymousId)
      .then((res) => {
        const approved = new Map(
          res.notifications
            .filter((n) => n.status === "approved")
            .map((n) => [n.meeting_id, n.application_id] as const)
        );
        setApprovedApplications(approved);
        setApplicationStatusByMeetingId(buildApplicationStatusMap(res.notifications));
      })
      .catch(() => {
        // 조회 실패는 조용히 넘어간다 — 채팅 버튼이 안 보이는 것 이상의 영향은 없다.
      });
  }, [profile?.anonymousId]);

  function hasChatAccess(meetingId: string): boolean {
    return ownedMeetingIds.has(meetingId) || approvedApplications.has(meetingId);
  }

  // 파티 탈퇴가 성공한 뒤 호출된다 — 이 모임에 대한 승인 상태를 지워서 채팅 접근권한과
  // 탈퇴 버튼이 다시 렌더링될 때 즉시 사라지게 하고, 모임 목록도 새로 불러와 참가 인원 표시를 갱신한다.
  function handleMeetingLeft(meetingId: string) {
    setApprovedApplications((prev) => {
      const next = new Map(prev);
      next.delete(meetingId);
      return next;
    });
    setApplicationStatusByMeetingId((prev) => {
      const next = new Map(prev);
      next.delete(meetingId);
      return next;
    });
    refreshMeetings().catch(() => {
      // 목록 갱신 실패는 조용히 넘어간다 — 다음 폴링에서 다시 시도된다.
    });
  }

  function handleChatProfileCreated(nextProfile: LocalProfile) {
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
    setProfile(nextProfile);
  }

  // 등록 직후 refetch(refreshMeetings)와 별개로, 다른 사람이 만든 모임도 놓치지 않게
  // 주기적으로 목록을 갱신한다(신청 화면이 열려 있을 땐 목록이 밑에서 바뀌어도
  // 사용자 입력을 방해하지 않도록 건드리지 않는다).
  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(() => {
      if (selected || showCreateSheet || manageMeeting) return;
      getMeetingsData()
        .then((refreshed) => {
          if (!cancelled) setMeetings(refreshed.meetings);
        })
        .catch(() => {
          // 폴링 실패는 조용히 넘어가고 다음 주기에 다시 시도한다.
        });
    }, MEETINGS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, showCreateSheet, manageMeeting]);

  useEffect(() => {
    if (!manageMeeting) return;
    let cancelled = false;
    function load() {
      if (!manageMeeting) return;
      getMeetingStatus(manageMeeting.id).then((next) => {
        if (!cancelled) setManageStatus(next);
      });
    }
    load();
    const timer = setInterval(load, STATUS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [manageMeeting]);

  // 참가자 알림 배너(ApplicantNotificationBanner)를 눌러 /meetings?notifications=1로
  // 들어온 경우, 신청 알림 시트를 자동으로 열어준다.
  useEffect(() => {
    if (searchParams.get("notifications") === "1") {
      openNotifications();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleMeetings = useMemo(() => {
    // 카테고리 필터를 먼저 적용하고, 검색어를 AND로 겹쳐 좁힌다.
    // 카톡 수집 파티는 '오픈채팅' 필터에서만 보여준다 — '전체'를 포함한 나머지 필터는
    // 서비스에서 직접 만든 파티만 다룬다(홈 미리보기는 지금처럼 섞어서 보여준다).
    let filtered = meetings.filter((meeting) => meeting.source !== "kakao_chat");
    if (activeFilter === "오픈채팅") {
      filtered = meetings.filter((meeting) => meeting.source === "kakao_chat");
    } else if (activeFilter !== "전체") {
      const categories = FILTER_TO_CATEGORIES[activeFilter] ?? [];
      filtered = filtered.filter((meeting) => categories.includes(meeting.category));
    }

    // 목록 전체를 이미 받아왔으므로 검색은 프론트 필터링으로 충분하다(새 API 불필요).
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) return filtered;

    return filtered.filter((meeting) =>
      [meeting.title, meeting.place_label, meeting.host.nickname].some((field) =>
        field?.toLowerCase().includes(keyword),
      ),
    );
  }, [activeFilter, meetings, searchKeyword]);

  // 카테고리 필터나 검색어가 바뀌면 1페이지로 되돌린다.
  const {
    page,
    totalPages,
    pageItems: pagedMeetings,
    goToPage,
    listTopRef,
  } = usePagination(visibleMeetings, `${activeFilter}|${searchKeyword.trim()}`);

  async function refreshMeetings() {
    const refreshed = await getMeetingsData();
    setMeetings(refreshed.meetings);
  }

  async function apply() {
    if (!selected || nickname.trim().length < 2 || !privacyChecked) return;

    setBusy(true);
    setResult(null);

    try {
      let currentProfile = profile;
      if (!currentProfile) {
        const created = await createNickname(nickname.trim());
        currentProfile = {
          profileId: created.profile_id,
          nickname: created.nickname,
          anonymousId: created.anonymous_id,
        };
        window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(currentProfile));
        setProfile(currentProfile);
      }

      const application = await submitMeetingApplication(selected.id, {
        nickname: currentProfile.nickname,
        message: message.trim() || undefined,
        anonymous_id: currentProfile.anonymousId,
      });
      // 알림 재조회 없이도 카드에 바로 "대기중" 배지가 뜨도록 낙관적으로 반영한다.
      setApplicationStatusByMeetingId((prev) => new Map(prev).set(selected.id, "pending"));
      // 성공하면 신청 시트를 닫고 중앙 모달로 결과를 알린다(인라인 문구는 놓치기 쉽다).
      // 문구는 홈 화면과 동일하게 맞춘다 — 같은 동작에 다른 말이 나오면 어색하다.
      setSelected(null);
      setApplicationDone(`${application.public_alias} 님의 신청이 저장되었습니다. ${application.next_step}`);
    } catch {
      setResult("신청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  function openMeeting(meeting: HomeMeeting) {
    setSelected(meeting);
    setMessage("");
    setResult(null);
    setPrivacyChecked(false);
    setNickname(profile?.nickname ?? nickname);
  }

  function openCreateSheet() {
    setCreateNicknameDraft("");
    setShowCreateSheet(true);
  }

  function closeCreateSheet() {
    setShowCreateSheet(false);
    setCreateTitle("");
    setCreateDescription("");
    setCreatePlace("");
    setCreateCapacity(2);
    setCreateStartsAt(toDatetimeLocalValue(new Date()));
    setCreateEndsAt(toDatetimeLocalValue(new Date(Date.now() + 60 * 60 * 1000)));
    setCreateNicknameDraft("");
    setCreateError(null);
    setCreateResult(null);
    setCreateCopied(false);
  }

  async function saveCreateNickname() {
    if (createNicknameDraft.trim().length < 2) return;
    setCreateNicknameSaving(true);
    setCreateError(null);
    try {
      const created = await createNickname(createNicknameDraft.trim(), profile?.anonymousId);
      const nextProfile = {
        profileId: created.profile_id,
        nickname: created.nickname,
        anonymousId: created.anonymous_id,
      };
      window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
      setProfile(nextProfile);
    } catch {
      setCreateError("닉네임 저장에 실패했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setCreateNicknameSaving(false);
    }
  }

  async function submitCreate() {
    if (!profile) {
      setCreateError("먼저 닉네임을 설정해주세요");
      return;
    }
    if (createTitle.trim().length < 1 || createPlace.trim().length < 1) {
      setCreateError("제목과 만남의 장소를 모두 입력해주세요");
      return;
    }
    if (new Date(createEndsAt).getTime() <= new Date(createStartsAt).getTime()) {
      setCreateError("마감 시각은 시작 시각보다 늦어야 해요");
      return;
    }
    setCreateSubmitting(true);
    setCreateError(null);
    try {
      const created = await createMeeting({
        category: createCategory,
        title: createTitle.trim(),
        description: createDescription.trim() || undefined,
        place_label: createPlace.trim(),
        capacity: createCapacity,
        starts_at: createStartsAt,
        ends_at: createEndsAt,
        nickname: profile.nickname,
        anonymous_id: profile.anonymousId,
      });
      saveOwnerSecret(created.meeting_id, created.owner_secret);
      setCreateResult({ meetingId: created.meeting_id, ownerSecret: created.owner_secret });
      await refreshMeetings();
    } catch {
      setCreateError("등록에 실패했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setCreateSubmitting(false);
    }
  }

  function openManage(meeting: HomeMeeting) {
    setManageMeeting(meeting);
    setManageStatus(null);
    setManageApplications(null);
    setManageAuthorized(false);
    setManageCodeChecked(false);
    setManageDecisionError(null);
    setManageOwnerCode(getOwnerSecret(meeting.id) ?? "");
  }

  function closeManage() {
    setManageMeeting(null);
  }

  async function refreshApplications(code: string) {
    if (!manageMeeting) return;
    const res = await getMeetingApplications(manageMeeting.id, code || undefined);
    setManageApplications(res.applications);
    setManageAuthorized(res.authorized);
    setManageCodeChecked(true);
    // 다른 기기에서 관리 코드를 직접 입력해 인증에 성공한 경우도 이 기기에 저장해둔다
    // — 안 그러면 HostPendingBanner가 이 기기에서는 이 모임을 영영 모른다(놓치는 케이스).
    if (res.authorized && code) {
      saveOwnerSecret(manageMeeting.id, code);
    }
  }

  async function handleDecision(applicationId: string, action: "approve" | "reject") {
    if (!manageMeeting) return;
    const decide = action === "approve" ? approveMeetingApplication : rejectMeetingApplication;
    try {
      await decide(manageMeeting.id, applicationId, manageOwnerCode);
      setManageDecisionError(null);
      await refreshApplications(manageOwnerCode);
      getMeetingStatus(manageMeeting.id).then(setManageStatus);
    } catch (err) {
      setManageDecisionError(err instanceof Error ? err.message : "처리하지 못했어요");
      await refreshApplications(manageOwnerCode);
    }
  }

  const manageCapacityInfo = manageStatus
    ? formatCapacityStatus(manageStatus.approved_count, manageStatus.capacity, manageStatus.is_closed)
    : null;

  async function openNotifications() {
    setShowNotifications(true);
    setNotificationsError(null);
    if (!profile?.anonymousId) {
      setNotifications([]);
      return;
    }
    try {
      const res = await getMyApplicationNotifications(profile.anonymousId);
      setNotifications(res.notifications);
      // 알림을 실제로 열어봤으니 '새 알림' 배너 기준 시각을 지금으로 갱신한다.
      markNotificationsSeenNow();
    } catch {
      setNotificationsError("알림을 불러오지 못했어요");
    }
  }

  async function handleDeleteNotification(notification: ApplicantNotification) {
    if (!profile?.anonymousId) return;
    setNotificationBusyId(notification.application_id);
    try {
      await deleteMyApplication(notification.meeting_id, notification.application_id, profile.anonymousId);
      setNotifications((prev) => (prev ?? []).filter((n) => n.application_id !== notification.application_id));
    } catch (error) {
      setNotificationsError(error instanceof Error ? error.message : "삭제하지 못했어요");
    } finally {
      setNotificationBusyId(null);
    }
  }

  return (
    <MobileShell active="meetings" title="파티" subtitle="닉네임만 공개하고 가볍게 합류해요">
      <HostPendingBanner variant="inline" />
      <ApplicantNotificationBanner variant="inline" />
      <div className={styles.toolbar}>
        {data.filters.map((filter) => (
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

      <div className={styles.meetingSearch}>
        <Search size={16} aria-hidden="true" />
        <input
          aria-label="파티 검색"
          onChange={(event) => setSearchKeyword(event.target.value)}
          placeholder="파티 이름·장소·호스트 검색"
          type="search"
          value={searchKeyword}
        />
      </div>

      <div className={styles.actionRow}>
        <button className={styles.createMeetingButton} onClick={openCreateSheet} type="button">
          <Plus size={16} /> 파티 만들기
        </button>
        <button className={styles.notificationButton} onClick={openNotifications} type="button">
          <Bell size={16} /> 내 신청 알림
        </button>
      </div>

      <div ref={listTopRef} />

      <section className={styles.meetingList}>
        {visibleMeetings.length === 0 ? (
          <div className={styles.result}>
            {searchKeyword.trim() ? `'${searchKeyword.trim()}'와 맞는 파티가 없어요.` : "열려 있는 파티가 없어요."}
          </div>
        ) : null}
        {pagedMeetings.map((meeting) => {
          const Icon = getMeetingIcon(meeting.category);
          const isOwned = ownedMeetingIds.has(meeting.id);
          const isExternal = meeting.source === "kakao_chat";
          const applyState = describeApplicationStatus(applicationStatusByMeetingId.get(meeting.id));
          return (
            <article className={styles.card} key={meeting.id}>
              <div className={styles.time}>
                <CalendarClock size={18} />
                <strong>{formatTime(meeting.starts_at)}</strong>
                <span>~ {formatTime(meeting.ends_at)}</span>
              </div>
              <div className={styles.timelineDot} aria-hidden="true">
                <span />
              </div>
              <div className={styles.categoryBubble}>
                <Icon size={25} strokeWidth={2.2} />
              </div>
              <div className={styles.body}>
                {isExternal ? <span className={styles.externalBadge}>오픈채팅에서 온 글</span> : null}
                <h2>{meeting.title}</h2>
                <p className={styles.meta}>
                  <MapPin size={14} /> {meeting.place_label}
                </p>
                {isExternal ? null : <p className={styles.host}>호스트 {meeting.host.nickname}</p>}
              </div>
              <div className={styles.joinPanel}>
                {isExternal ? (
                  <button className={styles.button} onClick={() => openMeeting(meeting)} type="button">
                    자세히
                  </button>
                ) : (
                  <>
                    <b>
                      {meeting.approved_count}/{meeting.capacity}
                    </b>
                    <span>지금 합류 가능</span>
                    {isOwned ? (
                      <button className={styles.secondaryButton} onClick={() => openManage(meeting)} type="button">
                        관리
                      </button>
                    ) : null}
                    {hasChatAccess(meeting.id) ? (
                      <button
                        className={styles.secondaryButton}
                        onClick={() => setChatMeeting(meeting)}
                        type="button"
                      >
                        파티 채팅 보기
                      </button>
                    ) : null}
                    {/* 내가 만든 파티에는 신청 버튼을 아예 안 보여준다(disabled가 아니라
                        미표시 — 2026-07-10 셀프 신청 버그 수정, 사용자 명시 지시).
                        위의 "관리" 버튼이 호스트 표식을 이미 대신한다. */}
                    {isOwned ? null : (
                      <button
                        className={applyState.disabled ? styles.applyStatusBadge : styles.button}
                        disabled={applyState.disabled}
                        onClick={() => openMeeting(meeting)}
                        type="button"
                      >
                        {applyState.label}
                      </button>
                    )}
                  </>
                )}
              </div>
            </article>
          );
        })}
      </section>

      <Pagination onChange={goToPage} page={page} totalPages={totalPages} />

      {/* 오픈채팅 글은 입력 폼이 없는 단순 안내라 바텀시트가 아니라 화면 정중앙 모달로 띄운다. */}
      {selected && selected.source === "kakao_chat" ? (
        <CenterModal
          confirmLabel="닫기"
          description="오픈채팅방에서 자동으로 가져온 글이에요. 서비스 내 신청·승인 없이, 오픈채팅방에서 직접 참여해 주세요."
          onClose={() => setSelected(null)}
          title={selected.title}
        >
          <span className={styles.externalBadge}>오픈채팅에서 온 글</span>
          <span className={styles.externalPlace}>{selected.place_label}</span>
          {selected.description ? <p className={styles.externalOriginal}>{selected.description}</p> : null}
        </CenterModal>
      ) : null}

      {selected && selected.source !== "kakao_chat" ? (
        <div className={styles.sheetBackdrop} onClick={() => setSelected(null)}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <button className={styles.sheetClose} onClick={() => setSelected(null)} type="button" aria-label="닫기">
              <X size={20} />
            </button>
            <div className={styles.sheetGrip} />
            <div className={styles.sheetHero}>
              <span>
                <LockKeyhole size={14} /> 닉네임만 공개
              </span>
              <h2>{selected.title}</h2>
              <p>
                {selected.place_label} · {selected.approved_count}/{selected.capacity}명 참여 중
              </p>
            </div>
            {/* 만남의 장소를 지도로 확인할 수 있게 한다(카톡 수집 파티는 이 분기에 오지 않는다). */}
            <PlaceMapSection places={[{ title: selected.place_label }]} />
            <div className={styles.form}>
              <label className={styles.label} htmlFor="meeting-nickname">
                공개 닉네임
              </label>
              <input
                className={styles.input}
                id="meeting-nickname"
                maxLength={20}
                onChange={(event) => setNickname(event.target.value)}
                placeholder="예: 바당이"
                value={nickname}
              />
              <label className={styles.label} htmlFor="meeting-message">
                호스트에게 남길 말
              </label>
              <textarea
                className={styles.textarea}
                id="meeting-message"
                maxLength={160}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="선택 입력. 실명이나 연락처는 쓰지 마세요."
                value={message}
              />
              <button
                className={styles.checkRow}
                onClick={() => setPrivacyChecked((checked) => !checked)}
                type="button"
              >
                <span className={privacyChecked ? styles.checkActive : ""}>
                  {privacyChecked ? <CheckCircle2 size={16} /> : null}
                </span>
                신중하게 신청해 주세요. 승인 후 불참하면 기다리는 분들에게 피해가 갑니다.
              </button>
              {result ? <div className={styles.result}>{result}</div> : null}
            </div>
            <div className={styles.sheetActions}>
              <button className={styles.secondaryButton} onClick={() => setSelected(null)} type="button">
                닫기
              </button>
              <button
                className={styles.primaryButton}
                disabled={busy || nickname.trim().length < 2 || !privacyChecked}
                onClick={apply}
                type="button"
              >
                {busy ? "처리 중" : "신청 제출"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {showCreateSheet ? (
        <div className={styles.sheetBackdrop} onClick={closeCreateSheet}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <button className={styles.sheetClose} onClick={closeCreateSheet} type="button" aria-label="닫기">
              <X size={20} />
            </button>
            <div className={styles.sheetGrip} />
            <div className={styles.sheetHero}>
              <span>
                <Plus size={14} /> 파티 만들기
              </span>
              <h2>{createResult ? "등록 완료" : "새 파티 등록"}</h2>
              {!createResult ? <p>로그인 없이 4자리 관리 코드로 신청을 승인/거절할 수 있어요</p> : null}
            </div>

            {createResult ? (
              <div className={styles.form}>
                <p className={styles.ownerSecretLabel}>
                  <KeyRound size={14} /> 관리 코드
                </p>
                <p className={styles.ownerSecretCode}>{createResult.ownerSecret}</p>
                <p className={styles.meta}>나중에 신청 승인/거절할 때 필요해요. 이 기기엔 자동 저장했어요.</p>
                <button
                  className={styles.secondaryButton}
                  onClick={() => {
                    navigator.clipboard?.writeText(createResult.ownerSecret);
                    setCreateCopied(true);
                  }}
                  type="button"
                >
                  <Copy size={14} /> {createCopied ? "복사됨" : "코드 복사"}
                </button>
              </div>
            ) : (
              <div className={styles.form}>
                <label className={styles.label}>카테고리</label>
                <div className={styles.toolbar}>
                  {CREATE_CATEGORIES.map((category) => (
                    <button
                      className={`${styles.chip} ${createCategory === category.value ? styles.chipActive : ""}`}
                      key={category.value}
                      onClick={() => setCreateCategory(category.value)}
                      type="button"
                    >
                      {category.label}
                    </button>
                  ))}
                </div>

                <label className={styles.label} htmlFor="create-title">
                  제목
                </label>
                <input
                  className={styles.input}
                  id="create-title"
                  maxLength={60}
                  onChange={(event) => setCreateTitle(event.target.value)}
                  placeholder="예: 공항 → 서귀포 택시팟"
                  value={createTitle}
                />

                <label className={styles.label} htmlFor="create-description">
                  설명(선택)
                </label>
                <textarea
                  className={styles.textarea}
                  id="create-description"
                  maxLength={300}
                  onChange={(event) => setCreateDescription(event.target.value)}
                  placeholder="장소·시간·유의사항 등"
                  value={createDescription}
                />

                <label className={styles.label} htmlFor="create-place">
                  만남의 장소
                </label>
                <input
                  className={styles.input}
                  id="create-place"
                  maxLength={60}
                  onChange={(event) => setCreatePlace(event.target.value)}
                  placeholder="예: 제주공항 3번 게이트"
                  value={createPlace}
                />

                <label className={styles.label} htmlFor="create-capacity">
                  정원
                </label>
                <input
                  className={styles.input}
                  id="create-capacity"
                  min={1}
                  onChange={(event) => setCreateCapacity(Number(event.target.value))}
                  type="number"
                  value={createCapacity}
                />
                <p className={styles.meta}>
                  본인(방장) 제외 모집 인원이에요. 예: 정원 {createCapacity}명이면 방장 포함 총{" "}
                  {createCapacity + 1}명이 모여요.
                </p>

                <label className={styles.label} htmlFor="create-starts-at">
                  시작 날짜/시간 설정
                </label>
                <input
                  className={styles.input}
                  id="create-starts-at"
                  onChange={(event) => setCreateStartsAt(event.target.value)}
                  type="datetime-local"
                  value={createStartsAt}
                />

                <label className={styles.label} htmlFor="create-ends-at">
                  마감 날짜/시간 설정
                </label>
                <input
                  className={styles.input}
                  id="create-ends-at"
                  onChange={(event) => setCreateEndsAt(event.target.value)}
                  type="datetime-local"
                  value={createEndsAt}
                />

                {profile ? (
                  <p className={styles.meta}>호스트 닉네임: {profile.nickname}</p>
                ) : (
                  <>
                    <label className={styles.label} htmlFor="create-host-nickname">
                      닉네임 설정 (파티를 만들려면 먼저 필요해요)
                    </label>
                    <div className={styles.ownerCodeRow}>
                      <input
                        className={styles.input}
                        id="create-host-nickname"
                        maxLength={20}
                        onChange={(event) => setCreateNicknameDraft(event.target.value)}
                        placeholder="예: 바당이"
                        value={createNicknameDraft}
                      />
                      <button
                        className={styles.secondaryButton}
                        disabled={createNicknameDraft.trim().length < 2 || createNicknameSaving}
                        onClick={saveCreateNickname}
                        type="button"
                      >
                        {createNicknameSaving ? "저장 중" : "저장"}
                      </button>
                    </div>
                  </>
                )}

                {createError ? <div className={styles.result}>{createError}</div> : null}
              </div>
            )}

            <div className={styles.sheetActions}>
              <button className={styles.secondaryButton} onClick={closeCreateSheet} type="button">
                닫기
              </button>
              {!createResult ? (
                <button
                  className={styles.primaryButton}
                  disabled={createSubmitting || !profile}
                  onClick={submitCreate}
                  type="button"
                >
                  {createSubmitting ? "등록 중" : "등록하기"}
                </button>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {manageMeeting ? (
        <div className={styles.sheetBackdrop} onClick={closeManage}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <button className={styles.sheetClose} onClick={closeManage} type="button" aria-label="닫기">
              <X size={20} />
            </button>
            <div className={styles.sheetGrip} />
            <div className={styles.sheetHero}>
              <span>
                <KeyRound size={14} /> 내 파티 관리
              </span>
              <h2>{manageMeeting.title}</h2>
              {manageCapacityInfo ? (
                <p className={manageCapacityInfo.emphasize ? styles.emphasizeCapacity : undefined}>
                  모집 현황: {manageCapacityInfo.text}
                </p>
              ) : null}
            </div>

            <div className={styles.form}>
              <label className={styles.label} htmlFor="manage-owner-code">
                관리 코드
              </label>
              <div className={styles.ownerCodeRow}>
                <input
                  className={styles.input}
                  id="manage-owner-code"
                  maxLength={4}
                  onChange={(event) => setManageOwnerCode(event.target.value)}
                  placeholder="관리 코드 4자리"
                  value={manageOwnerCode}
                />
                <button
                  className={styles.secondaryButton}
                  onClick={() => refreshApplications(manageOwnerCode)}
                  type="button"
                >
                  확인
                </button>
              </div>

              {manageCodeChecked && !manageAuthorized ? (
                <div className={styles.result}>코드가 맞지 않아요</div>
              ) : null}
              {manageDecisionError ? <div className={styles.result}>{manageDecisionError}</div> : null}

              {manageApplications && manageApplications.length > 0 ? (
                <ul className={styles.applicantList}>
                  {manageApplications.map((application, index) => (
                    <li className={styles.applicantRow} key={application.application_id ?? index}>
                      <span>
                        {application.nickname}
                        {manageAuthorized && application.message ? (
                          <span className={styles.meta}> · {application.message}</span>
                        ) : null}
                      </span>
                      {manageAuthorized && application.application_id && application.status === "pending" ? (
                        <span className={styles.applicantActions}>
                          <button
                            className={styles.approveButton}
                            onClick={() => handleDecision(application.application_id!, "approve")}
                            type="button"
                          >
                            <Check size={13} /> 승인
                          </button>
                          <button
                            className={styles.rejectButton}
                            onClick={() => handleDecision(application.application_id!, "reject")}
                            type="button"
                          >
                            거절
                          </button>
                        </span>
                      ) : null}
                      {manageAuthorized && application.status === "approved" ? (
                        <span className={styles.approvedTag}>확정됨</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            <div className={styles.sheetActions}>
              <button className={styles.secondaryButton} onClick={closeManage} type="button">
                닫기
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {showNotifications ? (
        <div className={styles.sheetBackdrop} onClick={() => setShowNotifications(false)}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <button
              className={styles.sheetClose}
              onClick={() => setShowNotifications(false)}
              type="button"
              aria-label="닫기"
            >
              <X size={20} />
            </button>
            <div className={styles.sheetGrip} />
            <div className={styles.sheetHero}>
              <span>
                <Bell size={14} /> 내 신청 알림
              </span>
              <h2>신청한 파티 상태</h2>
            </div>

            <div className={styles.form}>
              {!profile ? (
                <div className={styles.result}>아직 신청한 파티가 없어요. 먼저 파티에 신청해보세요.</div>
              ) : null}
              {notificationsError ? <div className={styles.result}>{notificationsError}</div> : null}

              {notifications && notifications.length > 0 ? (
                <ul className={styles.applicantList}>
                  {notifications.map((notification) => (
                    <li className={styles.notificationRow} key={notification.application_id}>
                      <div>
                        <p className={styles.notificationTitle}>{notification.title}</p>
                        <p className={styles.meta}>{notification.body}</p>
                        <p className={styles.meta}>
                          {notification.meeting_title} · {notification.place_label} · 호스트{" "}
                          {notification.host_nickname}
                        </p>
                      </div>
                      <button
                        className={styles.rejectButton}
                        disabled={notificationBusyId === notification.application_id}
                        onClick={() => handleDeleteNotification(notification)}
                        type="button"
                      >
                        <Trash2 size={13} /> 삭제
                      </button>
                    </li>
                  ))}
                </ul>
              ) : profile && notifications ? (
                <div className={styles.result}>아직 신청한 파티가 없어요.</div>
              ) : null}
            </div>

            <div className={styles.sheetActions}>
              <button className={styles.secondaryButton} onClick={() => setShowNotifications(false)} type="button">
                닫기
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {chatMeeting ? (
        <ChatSheet
          meetingId={chatMeeting.id}
          meetingTitle={chatMeeting.title}
          meetingPlaceLabel={chatMeeting.place_label}
          hasAccess={hasChatAccess(chatMeeting.id)}
          profile={profile}
          onProfileCreated={handleChatProfileCreated}
          myApplicationId={approvedApplications.get(chatMeeting.id)}
          onLeft={() => handleMeetingLeft(chatMeeting.id)}
          onClose={() => setChatMeeting(null)}
        />
      ) : null}

      {applicationDone ? (
        <CenterModal
          description={applicationDone}
          onClose={() => setApplicationDone(null)}
          title="신청 접수 완료"
        />
      ) : null}
    </MobileShell>
  );
}
