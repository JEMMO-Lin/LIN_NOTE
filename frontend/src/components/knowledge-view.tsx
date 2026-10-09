"use client";

import { useState } from "react";
import {
  ArrowRightOutlined,
  BranchesOutlined,
  BulbOutlined,
  MessageOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Empty,
  Input,
  Segmented,
  Skeleton,
  Tag,
  Typography,
} from "antd";

import { ApiError, knowledgeApi } from "@/services/api";
import type {
  AskResponse,
  KnowledgeBase,
  KnowledgeTree,
} from "@/types";

type Props = {
  knowledgeBase: KnowledgeBase | null;
  onOpenContent: (id: string) => void;
};

export function KnowledgeView({ knowledgeBase, onOpenContent }: Props) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<"tree" | "ask">("tree");
  const [tree, setTree] = useState<KnowledgeTree | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [asking, setAsking] = useState(false);

  const loadTree = async () => {
    if (!knowledgeBase || treeLoading) return;
    setTreeLoading(true);
    try {
      const result = await knowledgeApi.tree(knowledgeBase.id);
      setTree(result.data);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "知识树加载失败");
    } finally {
      setTreeLoading(false);
    }
  };

  const changeMode = (value: "tree" | "ask") => {
    setMode(value);
    if (value === "tree" && !tree) void loadTree();
  };

  const ask = async () => {
    if (!question.trim()) {
      message.info("先输入一个问题");
      return;
    }
    setAsking(true);
    try {
      const result = await knowledgeApi.ask({
        question: question.trim(),
        kb_id: knowledgeBase?.id,
        top_k: 8,
      });
      setAnswer(result.data);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "回答生成失败");
    } finally {
      setAsking(false);
    }
  };

  if (!knowledgeBase) {
    return <Empty description="创建知识库后即可生成知识树和进行问答" />;
  }

  return (
    <div className="knowledge-view view-enter">
      <div className="knowledge-heading">
        <div>
          <span className="eyebrow">CONNECTED KNOWLEDGE</span>
          <Typography.Title>看见知识之间的联系。</Typography.Title>
          <Typography.Paragraph>
            浏览「{knowledgeBase.name}」的知识脉络，或直接向自己的资料提问。
          </Typography.Paragraph>
        </div>
        <Segmented
          value={mode}
          onChange={(value) => changeMode(value as "tree" | "ask")}
          options={[
            { label: "知识树", value: "tree", icon: <BranchesOutlined /> },
            { label: "知识问答", value: "ask", icon: <MessageOutlined /> },
          ]}
        />
      </div>

      {mode === "tree" ? (
        <section className="tree-panel">
          {!tree && !treeLoading ? (
            <div className="tree-empty">
              <span className="tree-seed"><BranchesOutlined /></span>
              <Typography.Title level={3}>从知识点长出脉络</Typography.Title>
              <Typography.Paragraph type="secondary">
                系统会按分类与显式关联，把已经提取的知识点组织成可浏览的结构。
              </Typography.Paragraph>
              <Button type="primary" onClick={loadTree}>生成知识树</Button>
            </div>
          ) : treeLoading ? (
            <Skeleton active paragraph={{ rows: 8 }} />
          ) : tree?.nodes.length ? (
            <KnowledgeMap tree={tree} onOpenContent={onOpenContent} />
          ) : (
            <Empty description="当前还没有知识点，先添加并整理一些内容" />
          )}
        </section>
      ) : (
        <section className="ask-panel">
          <div className="ask-composer">
            <Input.TextArea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onPressEnter={(event) => {
                if (!event.shiftKey) {
                  event.preventDefault();
                  void ask();
                }
              }}
              placeholder="例如：这些资料对做好用户访谈有哪些共同建议？"
              autoSize={{ minRows: 3, maxRows: 6 }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={asking}
              onClick={ask}
            >
              向知识库提问
            </Button>
          </div>
          {asking ? (
            <div className="answer-card"><Skeleton active paragraph={{ rows: 4 }} /></div>
          ) : answer ? (
            <div className="answer-card">
              <div className="answer-label">
                <BulbOutlined />
                {answer.wiki_hit ? "LLM Wiki 直接命中" : "基于原始文档生成"}
                {answer.wiki_created && <Tag color="green">已沉淀到 Wiki</Tag>}
                {!answer.wiki_hit && answer.ask_count > 1 && (
                  <Tag bordered={false}>同类问题第 {answer.ask_count} 次</Tag>
                )}
              </div>
              <Typography.Paragraph className="answer-text">
                {answer.answer}
              </Typography.Paragraph>
              {answer.sources.length > 0 && (
                <div className="answer-sources">
                  <span>参考知识点</span>
                  {answer.sources.map((source) => (
                    <button
                      key={source.point_id}
                      onClick={() => source.content_id && onOpenContent(source.content_id)}
                    >
                      <strong>{source.title}</strong>
                      <Tag bordered={false}>{Math.round(source.score * 100)}%</Tag>
                      <ArrowRightOutlined />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="ask-empty">
              <MessageOutlined />
              <span>答案只会依据你保存的知识点生成，并附上参考来源。</span>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function KnowledgeMap({
  tree,
  onOpenContent,
}: {
  tree: KnowledgeTree;
  onOpenContent: (id: string) => void;
}) {
  const groups = tree.nodes.reduce<Record<string, KnowledgeTree["nodes"]>>(
    (result, node) => {
      const category = node.category || "未分类";
      result[category] ||= [];
      result[category].push(node);
      return result;
    },
    {},
  );

  return (
    <div className="knowledge-map">
      {Object.entries(groups).map(([category, nodes], index) => (
        <article className={`knowledge-cluster cluster-${index % 4}`} key={category}>
          <div className="cluster-heading">
            <span />
            <strong>{category}</strong>
            <small>{nodes.length} 个知识点</small>
          </div>
          <div className="cluster-nodes">
            {nodes.map((node) => (
              <button
                key={node.id}
                onClick={() => node.content_id && onOpenContent(node.content_id)}
              >
                <span
                  className="importance-ring"
                  style={{ "--importance": node.importance } as React.CSSProperties}
                />
                <strong>{node.label}</strong>
                <ArrowRightOutlined />
              </button>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}
