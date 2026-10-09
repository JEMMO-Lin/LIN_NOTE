"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BulbOutlined,
  BranchesOutlined,
  MenuOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { App, Button, Modal, Skeleton } from "antd";

import { ContentDetailDrawer } from "@/components/content-detail-drawer";
import { ImportDrawer } from "@/components/import-drawer";
import { KnowledgeBaseModal } from "@/components/knowledge-base-modal";
import { KnowledgeView } from "@/components/knowledge-view";
import { OverviewView } from "@/components/overview-view";
import { SearchView } from "@/components/search-view";
import { SettingsView } from "@/components/settings-view";
import { Sidebar, type WorkspaceView } from "@/components/sidebar";
import { TemplatesView } from "@/components/templates-view";
import {
  ApiError,
  contentApi,
  knowledgeBaseApi,
} from "@/services/api";
import { useAppStore } from "@/stores/app-store";
import type {
  ContentItem,
  KnowledgeBase,
  KnowledgeBaseStats,
} from "@/types";

export function Workspace() {
  const router = useRouter();
  const { message, modal } = App.useApp();
  const hydrated = useAppStore((state) => state.hydrated);
  const token = useAppStore((state) => state.token);
  const knowledgeBases = useAppStore((state) => state.knowledgeBases);
  const activeKnowledgeBaseId = useAppStore(
    (state) => state.activeKnowledgeBaseId,
  );
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed);
  const signOut = useAppStore((state) => state.signOut);
  const setKnowledgeBases = useAppStore((state) => state.setKnowledgeBases);
  const setActiveKnowledgeBaseId = useAppStore(
    (state) => state.setActiveKnowledgeBaseId,
  );
  const setSidebarCollapsed = useAppStore(
    (state) => state.setSidebarCollapsed,
  );

  const [view, setView] = useState<WorkspaceView>("overview");
  const [loadingShell, setLoadingShell] = useState(true);
  const [loadingContents, setLoadingContents] = useState(false);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [contentTotal, setContentTotal] = useState(0);
  const [stats, setStats] = useState<KnowledgeBaseStats | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [kbModalOpen, setKbModalOpen] = useState(false);
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [selectedContentId, setSelectedContentId] = useState<string | null>(
    null,
  );
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  const activeKnowledgeBase = useMemo(
    () =>
      knowledgeBases.find((item) => item.id === activeKnowledgeBaseId) || null,
    [activeKnowledgeBaseId, knowledgeBases],
  );

  const handleSessionError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        signOut();
        message.info("登录状态已失效，请重新登录");
        router.replace("/login");
        return true;
      }
      return false;
    },
    [message, router, signOut],
  );

  const loadKnowledgeBases = useCallback(async () => {
    try {
      const result = await knowledgeBaseApi.list();
      setKnowledgeBases(result.data);
    } catch (error) {
      if (!handleSessionError(error)) {
        message.error(
          error instanceof ApiError ? error.message : "知识库加载失败",
        );
      }
    } finally {
      setLoadingShell(false);
    }
  }, [handleSessionError, message, setKnowledgeBases]);

  const loadActiveKnowledgeBase = useCallback(async () => {
    if (!activeKnowledgeBaseId) {
      setContents([]);
      setContentTotal(0);
      setStats(null);
      return;
    }
    setLoadingContents(true);
    try {
      const [contentResult, statsResult] = await Promise.all([
        contentApi.list(activeKnowledgeBaseId),
        knowledgeBaseApi.stats(activeKnowledgeBaseId),
      ]);
      setContents(contentResult.data);
      setContentTotal(contentResult.total);
      setStats(statsResult.data);
    } catch (error) {
      if (!handleSessionError(error)) {
        message.error(
          error instanceof ApiError ? error.message : "内容加载失败",
        );
      }
    } finally {
      setLoadingContents(false);
    }
  }, [activeKnowledgeBaseId, handleSessionError, message]);

  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    void loadKnowledgeBases();
  }, [hydrated, loadKnowledgeBases, router, token]);

  useEffect(() => {
    if (!token || loadingShell) return;
    const task = window.setTimeout(() => void loadActiveKnowledgeBase(), 0);
    return () => window.clearTimeout(task);
  }, [activeKnowledgeBaseId, loadActiveKnowledgeBase, loadingShell, token]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setView("search");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!hydrated || !token) return;
    const task = window.setTimeout(() => {
      setOnboardingOpen(
        window.localStorage.getItem("knowflow-onboarding-done") !== "true",
      );
    }, 0);
    return () => window.clearTimeout(task);
  }, [hydrated, token]);

  const openCreateKb = () => {
    setEditingKb(null);
    setKbModalOpen(true);
  };

  const openEditKb = (item: KnowledgeBase) => {
    setEditingKb(item);
    setKbModalOpen(true);
  };

  const savedKnowledgeBase = (item: KnowledgeBase) => {
    const exists = knowledgeBases.some((kb) => kb.id === item.id);
    const next = exists
      ? knowledgeBases.map((kb) => (kb.id === item.id ? item : kb))
      : [item, ...knowledgeBases];
    setKnowledgeBases(next);
    setActiveKnowledgeBaseId(item.id);
    setView("overview");
  };

  const deleteKnowledgeBase = (item: KnowledgeBase) => {
    modal.confirm({
      title: `删除「${item.name}」？`,
      content:
        "知识库里的内容和知识点也会一起删除，这个操作无法撤销。",
      okText: "确认删除",
      cancelText: "保留",
      okButtonProps: { danger: true },
      centered: true,
      async onOk() {
        try {
          await knowledgeBaseApi.remove(item.id);
          const next = knowledgeBases.filter((kb) => kb.id !== item.id);
          setKnowledgeBases(next);
          message.success("知识库已删除");
        } catch (error) {
          message.error(error instanceof ApiError ? error.message : "删除失败");
          throw error;
        }
      },
    });
  };

  const logout = () => {
    signOut();
    router.replace("/login");
  };

  const changeView = (nextView: WorkspaceView) => {
    setView(nextView);
    window.requestAnimationFrame(() =>
      window.scrollTo({ top: 0, behavior: "smooth" }),
    );
  };

  if (!hydrated || (token && loadingShell)) {
    return (
      <div className="app-loading">
        <div className="loading-brand">
          <span className="loading-seed" />
          <strong>KnowFlow</strong>
        </div>
        <Skeleton active paragraph={{ rows: 6 }} />
      </div>
    );
  }

  if (!token) return null;

  return (
    <main className={`workspace ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        collapsed={sidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        activeView={view}
        knowledgeBases={knowledgeBases}
        activeKnowledgeBaseId={activeKnowledgeBaseId}
        onCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onViewChange={changeView}
        onKnowledgeBaseChange={setActiveKnowledgeBaseId}
        onCreateKnowledgeBase={openCreateKb}
        onEditKnowledgeBase={openEditKb}
        onDeleteKnowledgeBase={deleteKnowledgeBase}
        onSignOut={logout}
      />

      <div className="workspace-main">
        <header className="mobile-header">
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={() => setMobileSidebarOpen(true)}
          />
          <strong>KnowFlow</strong>
          {activeKnowledgeBase && view === "overview" ? (
            <Button
              type="primary"
              shape="circle"
              icon={<PlusOutlined />}
              onClick={() => setImportOpen(true)}
            />
          ) : (
            <Button
              type="text"
              shape="circle"
              icon={<SearchOutlined />}
              onClick={() => setView("search")}
            />
          )}
        </header>

        <div className="workspace-scroll">
          {view === "overview" && (
            <OverviewView
              knowledgeBase={activeKnowledgeBase}
              stats={stats}
              contents={contents}
              total={contentTotal}
              loading={loadingContents}
              onImport={() => setImportOpen(true)}
              onCreateKnowledgeBase={openCreateKb}
              onOpenContent={setSelectedContentId}
              onRefresh={loadActiveKnowledgeBase}
            />
          )}
          {view === "search" && (
            <SearchView
              knowledgeBases={knowledgeBases}
              activeKnowledgeBaseId={activeKnowledgeBaseId}
              onOpenContent={setSelectedContentId}
            />
          )}
          {view === "knowledge" && (
            <KnowledgeView
              knowledgeBase={activeKnowledgeBase}
              onOpenContent={setSelectedContentId}
            />
          )}
          {view === "templates" && <TemplatesView />}
          {view === "settings" && (
            <SettingsView
              onSignOut={logout}
              knowledgeBase={activeKnowledgeBase}
            />
          )}
        </div>
      </div>

      <KnowledgeBaseModal
        open={kbModalOpen}
        editing={editingKb}
        onClose={() => setKbModalOpen(false)}
        onSaved={savedKnowledgeBase}
      />
      <ImportDrawer
        open={importOpen}
        knowledgeBase={activeKnowledgeBase}
        onClose={() => setImportOpen(false)}
        onImported={(item) => {
          setContents((current) => [item, ...current]);
          setContentTotal((current) => current + 1);
          setStats((current) =>
            current
              ? { ...current, content_count: current.content_count + 1 }
              : current,
          );
          window.setTimeout(() => void loadActiveKnowledgeBase(), 1800);
        }}
      />
      <ContentDetailDrawer
        contentId={selectedContentId}
        onClose={() => setSelectedContentId(null)}
        onDeleted={(id) => {
          setContents((current) => current.filter((item) => item.id !== id));
          setContentTotal((current) => Math.max(0, current - 1));
          setStats((current) =>
            current
              ? {
                  ...current,
                  content_count: Math.max(0, current.content_count - 1),
                }
              : current,
          );
        }}
        onUpdated={(updated) => {
          setContents((current) =>
            current.map((item) => (item.id === updated.id ? updated : item)),
          );
        }}
      />
      <Modal
        open={onboardingOpen}
        title={null}
        footer={null}
        closable={false}
        centered
        width={680}
        className="onboarding-modal"
      >
        <span className="onboarding-mark"><BulbOutlined /></span>
        <h2>欢迎来到 KnowFlow</h2>
        <p>用三步把零散内容变成会持续生长的知识体系。</p>
        <div className="onboarding-steps">
          <article><strong>01</strong><span><b>创建知识库</b>为一个长期关注的主题留出空间。</span></article>
          <article><strong>02</strong><span><b>收进内容</b>粘贴文本、链接，或上传一张截图。</span></article>
          <article><strong>03</strong><span><b>建立连接</b><BranchesOutlined /> 浏览知识树，或直接向资料提问。</span></article>
        </div>
        <Button
          type="primary"
          size="large"
          onClick={() => {
            window.localStorage.setItem("knowflow-onboarding-done", "true");
            setOnboardingOpen(false);
            if (!knowledgeBases.length) openCreateKb();
          }}
        >
          {knowledgeBases.length ? "开始探索" : "创建第一个知识库"}
        </Button>
      </Modal>
    </main>
  );
}
