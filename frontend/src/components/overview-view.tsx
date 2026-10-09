"use client";

import {
  ArrowRightOutlined,
  BookOutlined,
  FileImageOutlined,
  FileTextOutlined,
  LinkOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  StarOutlined,
} from "@ant-design/icons";
import {
  Button,
  Empty,
  Input,
  Pagination,
  Select,
  Skeleton,
  Tag,
  Typography,
} from "antd";
import { useMemo, useState } from "react";

import type {
  ContentItem,
  KnowledgeBase,
  KnowledgeBaseStats,
} from "@/types";
import {
  formatRelativeDate,
  parseApiDate,
  sourceMeta,
  truncate,
} from "@/utils/format";

type Props = {
  knowledgeBase: KnowledgeBase | null;
  stats: KnowledgeBaseStats | null;
  contents: ContentItem[];
  total: number;
  loading: boolean;
  onImport: () => void;
  onCreateKnowledgeBase: () => void;
  onOpenContent: (id: string) => void;
  onRefresh: () => void;
};

const PAGE_SIZE = 8;

export function OverviewView({
  knowledgeBase,
  stats,
  contents,
  total,
  loading,
  onImport,
  onCreateKnowledgeBase,
  onOpenContent,
  onRefresh,
}: Props) {
  const [keyword, setKeyword] = useState("");
  const [source, setSource] = useState("all");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    return contents.filter((item) => {
      const matchesSource = source === "all" || item.source_type === source;
      const matchesKeyword =
        !query ||
        item.title.toLowerCase().includes(query) ||
        item.summary?.toLowerCase().includes(query) ||
        item.original_text.toLowerCase().includes(query);
      return matchesSource && matchesKeyword;
    });
  }, [contents, keyword, source]);

  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const growth = useMemo(() => buildGrowthData(contents), [contents]);

  if (!knowledgeBase) {
    return (
      <div className="empty-workspace">
        <div className="empty-plant">
          <span className="plant-leaf leaf-left" />
          <span className="plant-leaf leaf-right" />
          <span className="plant-stem" />
        </div>
        <Typography.Title level={2}>种下第一个知识库</Typography.Title>
        <Typography.Paragraph type="secondary">
          为你正在学习、研究或热爱的主题创建一个空间，从第一条内容开始积累。
        </Typography.Paragraph>
        <Button type="primary" size="large" icon={<PlusOutlined />} onClick={onCreateKnowledgeBase}>
          新建知识库
        </Button>
      </div>
    );
  }

  return (
    <div className="overview-view view-enter">
      <section className="overview-hero">
        <div>
          <span className="eyebrow">
            {knowledgeBase.category || "MY KNOWLEDGE SPACE"}
          </span>
          <Typography.Title>
            {knowledgeBase.name}
            <span className="title-spark">✦</span>
          </Typography.Title>
          <Typography.Paragraph>
            {knowledgeBase.description || "把新发现收进来，让它们在这里慢慢连接、生长。"}
          </Typography.Paragraph>
          {knowledgeBase.tags.length > 0 && (
            <div className="hero-tags">
              {knowledgeBase.tags.map((tag) => (
                <Tag bordered={false} key={tag}>{tag}</Tag>
              ))}
            </div>
          )}
        </div>
        <Button
          type="primary"
          size="large"
          icon={<PlusOutlined />}
          onClick={onImport}
          className="hero-add-button"
        >
          添加内容
        </Button>
      </section>

      <section className="insight-grid">
        <article className="stat-card stat-card-sage">
          <div className="stat-icon"><BookOutlined /></div>
          <div>
            <span>收藏内容</span>
            <strong>{stats?.content_count ?? total}</strong>
            <small>条内容正在沉淀</small>
          </div>
        </article>
        <article className="stat-card stat-card-sky">
          <div className="stat-icon"><StarOutlined /></div>
          <div>
            <span>知识点</span>
            <strong>{stats?.knowledge_point_count ?? 0}</strong>
            <small>由 AI 提炼和连接</small>
          </div>
        </article>
        <article className="growth-card">
          <div className="growth-copy">
            <span>近 7 天生长</span>
            <strong>
              +{growth.reduce((sum, item) => sum + item.value, 0)}
              <small> 条</small>
            </strong>
          </div>
          <div className="mini-bars" aria-label="近七天内容增长">
            {growth.map((item) => (
              <div className="mini-bar-column" key={item.label}>
                <span
                  className="mini-bar"
                  style={{ height: `${Math.max(12, item.height)}%` }}
                  title={`${item.label}：${item.value} 条`}
                />
                <small>{item.label}</small>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="content-section">
        <div className="section-heading-row">
          <div>
            <Typography.Title level={3}>最近内容</Typography.Title>
            <Typography.Text type="secondary">
              共 {filtered.length} 条，继续回看会产生新的连接。
            </Typography.Text>
          </div>
          <Button type="text" icon={<ReloadOutlined />} onClick={onRefresh}>
            刷新
          </Button>
        </div>

        <div className="content-toolbar">
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="在当前知识库中筛选"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
          />
          <Select
            value={source}
            onChange={(value) => {
              setSource(value);
              setPage(1);
            }}
            options={[
              { value: "all", label: "全部来源" },
              { value: "text", label: "文本" },
              { value: "url", label: "链接" },
              { value: "image", label: "图片" },
            ]}
          />
        </div>

        {loading ? (
          <div className="content-grid">
            {[1, 2, 3, 4].map((item) => (
              <div className="content-card skeleton-card" key={item}>
                <Skeleton active paragraph={{ rows: 3 }} />
              </div>
            ))}
          </div>
        ) : visible.length ? (
          <>
            <div className="content-grid">
              {visible.map((item) => (
                <ContentCard key={item.id} item={item} onOpen={onOpenContent} />
              ))}
            </div>
            {filtered.length > PAGE_SIZE && (
              <Pagination
                current={page}
                pageSize={PAGE_SIZE}
                total={filtered.length}
                showSizeChanger={false}
                onChange={setPage}
                className="content-pagination"
              />
            )}
          </>
        ) : (
          <div className="content-empty">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={keyword || source !== "all" ? "没有符合筛选的内容" : "这里还空着，收进第一条内容吧"}
            >
              {!keyword && source === "all" && (
                <Button type="primary" icon={<PlusOutlined />} onClick={onImport}>
                  添加内容
                </Button>
              )}
            </Empty>
          </div>
        )}
      </section>
    </div>
  );
}

function ContentCard({
  item,
  onOpen,
}: {
  item: ContentItem;
  onOpen: (id: string) => void;
}) {
  const meta = sourceMeta[item.source_type] || sourceMeta.text;
  const icon =
    item.source_type === "url" ? (
      <LinkOutlined />
    ) : item.source_type === "image" ? (
      <FileImageOutlined />
    ) : (
      <FileTextOutlined />
    );

  return (
    <button className="content-card" onClick={() => onOpen(item.id)}>
      <div className="content-card-top">
        <span className={`content-source-icon ${meta.className}`}>{icon}</span>
        <span className="content-date">{formatRelativeDate(item.created_at)}</span>
      </div>
      <h3>{item.title}</h3>
      {item.summary ? (
        <p>{truncate(item.summary, 100)}</p>
      ) : (
        <div className={`processing-line ${item.status === "failed" || item.status === "cancelled" ? "is-failed" : ""}`}>
          <span />
          {item.status === "failed"
            ? "AI 整理未完成"
            : item.status === "cancelled"
              ? "AI 整理已停止"
              : item.status === "finalizing"
                ? "正在写入结果…"
                : "AI 正在提炼…"}
        </div>
      )}
      <div className="content-card-footer">
        <Tag bordered={false} className={`source-tag ${meta.className}`}>
          {meta.label}
        </Tag>
        <ArrowRightOutlined />
      </div>
    </button>
  );
}

function buildGrowthData(contents: ContentItem[]) {
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() - (6 - index));
    return {
      key: date.toISOString().slice(0, 10),
      label: new Intl.DateTimeFormat("zh-CN", { weekday: "short" })
        .format(date)
        .replace("周", ""),
      value: 0,
      height: 0,
    };
  });

  contents.forEach((item) => {
    const key = parseApiDate(item.created_at).toISOString().slice(0, 10);
    const day = days.find((entry) => entry.key === key);
    if (day) day.value += 1;
  });
  const max = Math.max(...days.map((day) => day.value), 1);
  return days.map((day) => ({
    ...day,
    height: Math.round((day.value / max) * 100),
  }));
}
