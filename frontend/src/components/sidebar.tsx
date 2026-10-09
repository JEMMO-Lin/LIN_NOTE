"use client";

import {
  AppstoreOutlined,
  BulbOutlined,
  BranchesOutlined,
  EditOutlined,
  EllipsisOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  SearchOutlined,
  SettingOutlined,
  FormOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Dropdown, Tooltip } from "antd";

import type { KnowledgeBase } from "@/types";

export type WorkspaceView =
  | "overview"
  | "search"
  | "knowledge"
  | "templates"
  | "settings";

type Props = {
  collapsed: boolean;
  mobileOpen: boolean;
  activeView: WorkspaceView;
  knowledgeBases: KnowledgeBase[];
  activeKnowledgeBaseId: string | null;
  onCollapse: () => void;
  onCloseMobile: () => void;
  onViewChange: (view: WorkspaceView) => void;
  onKnowledgeBaseChange: (id: string) => void;
  onCreateKnowledgeBase: () => void;
  onEditKnowledgeBase: (item: KnowledgeBase) => void;
  onDeleteKnowledgeBase: (item: KnowledgeBase) => void;
  onSignOut: () => void;
};

const colorClasses = ["sage", "sky", "peach", "lilac", "butter"];

export function Sidebar({
  collapsed,
  mobileOpen,
  activeView,
  knowledgeBases,
  activeKnowledgeBaseId,
  onCollapse,
  onCloseMobile,
  onViewChange,
  onKnowledgeBaseChange,
  onCreateKnowledgeBase,
  onEditKnowledgeBase,
  onDeleteKnowledgeBase,
  onSignOut,
}: Props) {
  const changeView = (view: WorkspaceView) => {
    onViewChange(view);
    onCloseMobile();
  };

  return (
    <>
      {mobileOpen && <button className="sidebar-scrim" onClick={onCloseMobile} />}
      <aside
        className={[
          "workspace-sidebar",
          collapsed ? "is-collapsed" : "",
          mobileOpen ? "is-mobile-open" : "",
        ].join(" ")}
      >
        <div className="sidebar-brand-row">
          <div className="sidebar-brand">
            <span className="brand-mark"><BulbOutlined /></span>
            {!collapsed && <span>KnowFlow</span>}
          </div>
          <Tooltip title={collapsed ? "展开侧栏" : "收起侧栏"} placement="right">
            <Button
              type="text"
              className="collapse-button"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={onCollapse}
            />
          </Tooltip>
        </div>

        <nav className="main-nav">
          <SidebarNavItem
            collapsed={collapsed}
            active={activeView === "overview"}
            icon={<AppstoreOutlined />}
            label="我的空间"
            onClick={() => changeView("overview")}
          />
          <SidebarNavItem
            collapsed={collapsed}
            active={activeView === "search"}
            icon={<SearchOutlined />}
            label="搜索知识"
            shortcut="⌘ K"
            onClick={() => changeView("search")}
          />
          <SidebarNavItem
            collapsed={collapsed}
            active={activeView === "knowledge"}
            icon={<BranchesOutlined />}
            label="知识脉络"
            onClick={() => changeView("knowledge")}
          />
          <SidebarNavItem
            collapsed={collapsed}
            active={activeView === "templates"}
            icon={<FormOutlined />}
            label="总结模板"
            onClick={() => changeView("templates")}
          />
        </nav>

        <div className="sidebar-divider" />

        <div className="kb-nav-section">
          {!collapsed && (
            <div className="sidebar-section-title">
              <span>知识库</span>
              <Tooltip title="新建知识库">
                <Button
                  type="text"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={onCreateKnowledgeBase}
                />
              </Tooltip>
            </div>
          )}
          {collapsed && (
            <Tooltip title="新建知识库" placement="right">
              <Button
                type="text"
                className="collapsed-add"
                icon={<PlusOutlined />}
                onClick={onCreateKnowledgeBase}
              />
            </Tooltip>
          )}

          <div className="kb-list">
            {knowledgeBases.map((kb, index) => {
              const active =
                activeView === "overview" && kb.id === activeKnowledgeBaseId;
              const item = (
                <button
                  key={kb.id}
                  className={`kb-nav-item ${active ? "active" : ""}`}
                  onClick={() => {
                    onKnowledgeBaseChange(kb.id);
                    changeView("overview");
                  }}
                >
                  <span
                    className={`kb-color-dot ${colorClasses[index % colorClasses.length]}`}
                  />
                  {!collapsed && (
                    <>
                      <span className="kb-nav-name">{kb.name}</span>
                      <Dropdown
                        trigger={["click"]}
                        menu={{
                          items: [
                            {
                              key: "edit",
                              label: "编辑",
                              icon: <EditOutlined />,
                              onClick: () => onEditKnowledgeBase(kb),
                            },
                            {
                              key: "delete",
                              label: "删除",
                              icon: <LogoutOutlined />,
                              danger: true,
                              onClick: () => onDeleteKnowledgeBase(kb),
                            },
                          ],
                        }}
                      >
                        <span
                          role="button"
                          tabIndex={0}
                          className="kb-more"
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                        >
                          <EllipsisOutlined />
                        </span>
                      </Dropdown>
                    </>
                  )}
                </button>
              );
              return collapsed ? (
                <Tooltip key={kb.id} title={kb.name} placement="right">
                  {item}
                </Tooltip>
              ) : item;
            })}
          </div>
        </div>

        <div className="sidebar-bottom">
          <SidebarNavItem
            collapsed={collapsed}
            active={activeView === "settings"}
            icon={<SettingOutlined />}
            label="设置"
            onClick={() => changeView("settings")}
          />
          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                {
                  key: "switch",
                  icon: <SwapOutlined />,
                  label: "切换账号",
                  onClick: onSignOut,
                },
                {
                  key: "logout",
                  icon: <LogoutOutlined />,
                  label: "退出登录",
                  onClick: onSignOut,
                },
              ],
            }}
          >
            <button className="sidebar-profile">
              <Avatar className="profile-avatar">K</Avatar>
              {!collapsed && (
                <span className="profile-copy">
                  <strong>我的知识空间</strong>
                  <small>本地私有空间</small>
                </span>
              )}
            </button>
          </Dropdown>
        </div>
      </aside>
    </>
  );
}

function SidebarNavItem({
  collapsed,
  active,
  icon,
  label,
  shortcut,
  onClick,
}: {
  collapsed: boolean;
  active: boolean;
  icon: React.ReactNode;
  label: string;
  shortcut?: string;
  onClick: () => void;
}) {
  const button = (
    <button className={`sidebar-nav-item ${active ? "active" : ""}`} onClick={onClick}>
      <span className="nav-icon">{icon}</span>
      {!collapsed && (
        <>
          <span>{label}</span>
          {shortcut && <kbd>{shortcut}</kbd>}
        </>
      )}
    </button>
  );
  return collapsed ? (
    <Tooltip title={label} placement="right">
      {button}
    </Tooltip>
  ) : button;
}
