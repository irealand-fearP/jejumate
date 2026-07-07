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
import { formatCapacityStatus } from "@/lib/format";
import { CATEGORY_TO_FILTER, FILTER_TO_CATEGORY } from "@/lib/meetingCategories";
import { getOwnerSecret, saveOwnerSecret } from "@/lib/ownerSecret";
import { HostPendingBanner } from "@/features/common/HostPendingBanner";
import { MobileShell } from "@/features/common/MobileShell";
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

const CREATE_CATEGORIES = [
  { value: "meal", label: "밥친구" },
  { value: "work", label: "작업" },
  { value: "move", label: "이동" },
  { value: "coffee", label: "커피챗" },
  { value: "run", label: "러닝" },
];

const DURATION_OPTIONS = [
  { label: "30분", minutes: 30 },
  { label: "1시간", minutes: 60 },
  { label: "2시간", minutes: 120 },
];

function getMeetingIcon(category: string) {
  return categoryIcon[category] ?? UsersRound;
}

export function MeetingsScreen({ data }: { data: MeetingsData }) {
  const searchParams = useSearchParams();
  const [meetings, setMeetings] = useState(data.meetings);
  const [activeFilter, setActiveFilter] = useState(() => {
    const categoryParam = searchParams.get("category");
    const filterFromCategory = categoryParam ? CATEGORY_TO_FILTER[categoryParam] : undefined;
    if (filterFromCategory && data.filters.includes(filterFromCategory)) return filterFromCategory;
    return data.filters[0] ?? "전체";
  });
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
  const [createDuration, setCreateDuration] = useState(60);
  const [createNicknameValue, setCreateNicknameValue] = useState(profile?.nickname ?? "");
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

  useEffect(() => {
    const owned = new Set<string>();
    for (const meeting of meetings) {
      if (getOwnerSecret(meeting.id)) owned.add(meeting.id);
    }
    setOwnedMeetingIds(owned);
  }, [meetings]);

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

  const visibleMeetings = useMemo(() => {
    if (activeFilter === "전체") return meetings;
    return meetings.filter((meeting) => meeting.category === FILTER_TO_CATEGORY[activeFilter]);
  }, [activeFilter, meetings]);

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
      setResult(`${application.public_alias} 님의 신청이 접수됐습니다. ${application.next_step}`);
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
    setCreateNicknameValue(profile?.nickname ?? createNicknameValue);
    setShowCreateSheet(true);
  }

  function closeCreateSheet() {
    setShowCreateSheet(false);
    setCreateTitle("");
    setCreateDescription("");
    setCreatePlace("");
    setCreateCapacity(2);
    setCreateDuration(60);
    setCreateError(null);
    setCreateResult(null);
    setCreateCopied(false);
  }

  async function submitCreate() {
    if (createTitle.trim().length < 1 || createPlace.trim().length < 1 || createNicknameValue.trim().length < 2) {
      setCreateError("제목, 장소, 닉네임을 모두 입력해주세요");
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
        duration_minutes: createDuration,
        nickname: createNicknameValue.trim(),
        anonymous_id: profile?.anonymousId,
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
    <MobileShell active="meetings" title="모임" subtitle="닉네임만 공개하고 가볍게 합류해요">
      <HostPendingBanner variant="inline" />
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

      <div className={styles.notice}>{data.privacy_note}</div>

      <div className={styles.actionRow}>
        <button className={styles.createMeetingButton} onClick={openCreateSheet} type="button">
          <Plus size={16} /> 모임 만들기
        </button>
        <button className={styles.notificationButton} onClick={openNotifications} type="button">
          <Bell size={16} /> 내 신청 알림
        </button>
      </div>

      <section className={styles.meetingList}>
        {visibleMeetings.map((meeting) => {
          const Icon = getMeetingIcon(meeting.category);
          const isOwned = ownedMeetingIds.has(meeting.id);
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
                <h2>{meeting.title}</h2>
                <p className={styles.meta}>
                  <MapPin size={14} /> {meeting.place_label}
                </p>
                <p className={styles.host}>호스트 {meeting.host.nickname}</p>
              </div>
              <div className={styles.joinPanel}>
                <b>
                  {meeting.approved_count}/{meeting.capacity}
                </b>
                <span>지금 합류 가능</span>
                {isOwned ? (
                  <button className={styles.secondaryButton} onClick={() => openManage(meeting)} type="button">
                    관리
                  </button>
                ) : null}
                <button className={styles.button} onClick={() => openMeeting(meeting)} type="button">
                  신청
                </button>
              </div>
            </article>
          );
        })}
      </section>

      {selected ? (
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
                실명과 연락처를 메시지에 적지 않았습니다.
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
                <Plus size={14} /> 모임 만들기
              </span>
              <h2>{createResult ? "등록 완료" : "새 모임 등록"}</h2>
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
                  장소
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

                <label className={styles.label}>마감 시간</label>
                <div className={styles.toolbar}>
                  {DURATION_OPTIONS.map((option) => (
                    <button
                      className={`${styles.chip} ${createDuration === option.minutes ? styles.chipActive : ""}`}
                      key={option.minutes}
                      onClick={() => setCreateDuration(option.minutes)}
                      type="button"
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                <label className={styles.label} htmlFor="create-nickname">
                  호스트 닉네임
                </label>
                <input
                  className={styles.input}
                  id="create-nickname"
                  maxLength={20}
                  onChange={(event) => setCreateNicknameValue(event.target.value)}
                  placeholder="예: 바당이"
                  value={createNicknameValue}
                />

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
                  disabled={createSubmitting}
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
                <KeyRound size={14} /> 내 모임 관리
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
              <h2>신청한 모임 상태</h2>
            </div>

            <div className={styles.form}>
              {!profile ? (
                <div className={styles.result}>아직 신청한 모임이 없어요. 먼저 모임에 신청해보세요.</div>
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
                <div className={styles.result}>아직 신청한 모임이 없어요.</div>
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
    </MobileShell>
  );
}
