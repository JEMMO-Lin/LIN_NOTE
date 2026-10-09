"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRightOutlined,
  BulbOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Empty,
  Input,
  Segmented,
  Select,
  Skeleton,
  Tag,
  Typography,
} from "antd";

import { ApiError, searchApi } from "@/services/api";
import type { KnowledgeBase, SearchMode, SearchResult } from "@/types";
import { truncate } from "@/utils/format";

type Props = {
  knowledgeBases: KnowledgeBase[];
  activeKnowledgeBaseId: string | null;
  onOpenContent: (id: string) => void;
};

export function SearchView({
  knowledgeBases,
  activeKnowledgeBaseId,
  onOpenContent,
}: Props) {
  const { message } = App.useApp();
  const inputRef = useRef<import("antd").InputRef>(null);
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<"current" | "all">("current");
  const [kbId, setKbId] = useState(activeKnowledgeBaseId);
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const search = async () => {
    if (!query.trim()) {
      message.info("输入想找的知识或问题");
      inputRef.current?.focus();
      return;
    }
    setLoading(true);
    setSearched(true);
    try {
      const result = await searchApi.search({
        query: query.trim(),
        kb_id: scope === "current" ? kbId || undefined : undefined,
        mode,
        top_k: 20,
      });
      setResults(result.data);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-view view-enter">
      <div className="search-heading">
        <span className="eyebrow">FIND THE RIGHT IDEA</span>
        <Typography.Title>在你的知识里，找到答案。</Typography.Title>
        <Typography.Paragraph>
          既能匹配关键词，也能理解相近的意思。
        </Typography.Paragraph>
      </div>

      <div className="search-box">
        <Input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onPressEnter={search}
          prefix={<SearchOutlined />}
          placeholder="例如：我收藏过哪些关于用户访谈的方法？"
          suffix={
            <Button type="primary" icon={<ArrowRightOutlined />} onClick={search}>
              搜索
            </Button>
          }
        />
        <div className="search-options">
          <Segmented
            value={scope}
            onChange={(value) => setScope(value as "current" | "all")}
            options={[
              { label: "当前知识库", value: "current" },
              { label: "全部知识库", value: "all" },
            ]}
          />
          {scope === "current" && (
            <Select
              value={kbId}
              onChange={setKbId}
              placeholder="选择知识库"
              options={knowledgeBases.map((kb) => ({
                value: kb.id,
                label: kb.name,
              }))}
            />
          )}
          <Select<SearchMode>
            value={mode}
            onChange={setMode}
            options={[
              { value: "hybrid", label: "智能混合" },
              { value: "keyword", label: "精确关键词" },
              { value: "vector", label: "语义相近" },
            ]}
          />
        </div>
      </div>

      {!searched ? (
        <section className="search-suggestions">
          <div className="suggestion-card suggestion-mint">
            <ThunderboltOutlined />
            <strong>用问题来搜索</strong>
            <span>不必记得原文，描述你想知道的内容就好。</span>
          </div>
          <div className="suggestion-card suggestion-sky">
            <BulbOutlined />
            <strong>发现隐含连接</strong>
            <span>语义检索会找到措辞不同、含义相近的知识点。</span>
          </div>
        </section>
      ) : (
        <section className="search-results">
          <div className="section-heading-row">
            <div>
              <Typography.Title level={3}>搜索结果</Typography.Title>
              <Typography.Text type="secondary">
                {loading ? "正在理解你的问题…" : `找到 ${results.length} 个相关知识点`}
              </Typography.Text>
            </div>
          </div>
          {loading ? (
            <div className="result-list">
              {[1, 2, 3].map((item) => (
                <div className="result-card" key={item}>
                  <Skeleton active paragraph={{ rows: 2 }} />
                </div>
              ))}
            </div>
          ) : results.length ? (
            <div className="result-list">
              {results.map((result, index) => (
                <button
                  className="result-card"
                  key={`${result.point_id}-${index}`}
                  onClick={() => result.content_id && onOpenContent(result.content_id)}
                  disabled={!result.content_id}
                >
                  <div className="result-rank">{String(index + 1).padStart(2, "0")}</div>
                  <div className="result-copy">
                    <div className="result-title-row">
                      <h3>{result.title}</h3>
                      <Tag bordered={false}>
                        相关度 {Math.round(Math.min(1, result.score) * 100)}%
                      </Tag>
                    </div>
                    <p>{truncate(result.content, 180)}</p>
                  </div>
                  <ArrowRightOutlined />
                </button>
              ))}
            </div>
          ) : (
            <div className="content-empty">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂时没有找到相关内容，换个说法试试"
              />
            </div>
          )}
        </section>
      )}
    </div>
  );
}
