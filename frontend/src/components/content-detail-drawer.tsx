"use client";

import { useEffect, useRef, useState } from "react";
import {
  BranchesOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  LinkOutlined,
  LoadingOutlined,
  MergeCellsOutlined,
  ReloadOutlined,
  SaveOutlined,
  StarOutlined,
  StopOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Checkbox,
  Collapse,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Skeleton,
  Tag,
  Typography,
} from "antd";

import {
  ApiError,
  contentApi,
  knowledgeApi,
  mergeApi,
} from "@/services/api";
import type {
  ContentItem,
  KnowledgePoint,
  MergePreview,
  SimilarContent,
} from "@/types";
import { formatFullDate, sourceMeta } from "@/utils/format";

type Props = {
  contentId: string | null;
  onClose: () => void;
  onDeleted: (id: string) => void;
  onUpdated?: (item: ContentItem) => void;
};

type ReprocessState =
  | "idle"
  | "starting"
  | "running"
  | "cancelling"
  | "cancelled"
  | "success"
  | "error";

export function ContentDetailDrawer({
  contentId,
  onClose,
  onDeleted,
  onUpdated,
}: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [item, setItem] = useState<ContentItem | null>(null);
  const [points, setPoints] = useState<KnowledgePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [reprocessState, setReprocessState] = useState<ReprocessState>("idle");
  const [reprocessMessage, setReprocessMessage] = useState("");
  const [editing, setEditing] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [similar, setSimilar] = useState<SimilarContent[]>([]);
  const [selectedSimilar, setSelectedSimilar] = useState<string[]>([]);
  const [mergePreview, setMergePreview] = useState<MergePreview | null>(null);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [editingPointId, setEditingPointId] = useState<string | null>(null);
  const [pointDraft, setPointDraft] = useState({ title: "", content: "" });
  const successTimerRef = useRef<number | null>(null);
  const onUpdatedRef = useRef(onUpdated);

  useEffect(() => {
    onUpdatedRef.current = onUpdated;
  }, [onUpdated]);

  useEffect(() => {
    return () => {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
      }
    };
  }, []);

  const load = async (id: string) => {
    setLoading(true);
    try {
      const result = await contentApi.detail(id);
      setItem(result.data);
      const pointResult = await knowledgeApi.points(result.data.kb_id, id);
      setPoints(pointResult.data);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "内容加载失败");
    } finally {
      setLoading(false);
    }
  };

  const processAgain = async () => {
    if (
      !item ||
      item.status === "pending" ||
      item.status === "finalizing" ||
      reprocessState === "starting"
    ) return;
    setReprocessState("starting");
    setReprocessMessage("");
    try {
      const result = await contentApi.process(item.id);
      setItem(result.data);
      onUpdatedRef.current?.(result.data);
      setReprocessState("running");
    } catch (error) {
      setReprocessMessage(
        error instanceof ApiError
          ? `${error.message}。请检查后端状态后再次尝试。`
          : "整理任务没有启动。请检查后端连接后再次尝试。",
      );
      setReprocessState("error");
    }
  };

  const cancelProcessing = async () => {
    if (!item || item.status !== "pending" || reprocessState === "cancelling") return;
    setReprocessState("cancelling");
    setReprocessMessage("正在通知后台停止任务，未完成的结果不会写入知识库。");
    try {
      const result = await contentApi.cancelProcessing(item.id);
      setItem(result.data);
      onUpdatedRef.current?.(result.data);
      setReprocessState("cancelled");
      setReprocessMessage("整理已停止，原有摘要和知识点保持不变。");
    } catch (error) {
      setReprocessState("running");
      setReprocessMessage(
        error instanceof ApiError
          ? `${error.message}。任务可能仍在运行，请稍后再试。`
          : "停止请求没有成功，任务可能仍在运行，请检查后端连接后再试。",
      );
    }
  };

  useEffect(() => {
    if (
      !contentId ||
      (item?.status !== "pending" && item?.status !== "finalizing")
    ) return;

    let cancelled = false;
    let pollTimer: number | null = null;
    let failedPolls = 0;
    let pollCount = 0;

    const schedulePoll = () => {
      pollTimer = window.setTimeout(async () => {
        try {
          const result = await contentApi.detail(contentId);
          if (cancelled) return;

          failedPolls = 0;
          pollCount += 1;

          if (result.data.status === "processed") {
            const pointResult = await knowledgeApi.points(
              result.data.kb_id,
              result.data.id,
            );
            if (cancelled) return;
            setItem(result.data);
            setPoints(pointResult.data);
            onUpdatedRef.current?.(result.data);
            setReprocessMessage("");
            setReprocessState("success");
            if (successTimerRef.current !== null) {
              window.clearTimeout(successTimerRef.current);
            }
            successTimerRef.current = window.setTimeout(
              () => setReprocessState("idle"),
              4500,
            );
            return;
          }

          if (result.data.status === "failed") {
            setItem(result.data);
            onUpdatedRef.current?.(result.data);
            setReprocessMessage(
              "AI 整理没有完成。后端已记录具体原因，请检查模型配置或运行日志后再次尝试。",
            );
            setReprocessState("error");
            return;
          }

          if (result.data.status === "cancelled") {
            setItem(result.data);
            onUpdatedRef.current?.(result.data);
            setReprocessMessage("整理已停止，未完成的结果没有写入知识库。");
            setReprocessState("cancelled");
            return;
          }

          setItem(result.data);
          onUpdatedRef.current?.(result.data);
          setReprocessState("running");
          setReprocessMessage(
            pollCount >= 80
              ? "整理用时较长，任务仍在后台运行；你可以保持页面打开或稍后再回来查看。"
              : "",
          );
          schedulePoll();
        } catch {
          if (cancelled) return;
          failedPolls += 1;
          setReprocessState("running");
          if (failedPolls >= 3) {
            setReprocessMessage("暂时无法读取整理进度，正在自动重试。请确认后端仍在运行。");
          }
          schedulePoll();
        }
      }, 1500);
    };

    schedulePoll();

    return () => {
      cancelled = true;
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
  }, [contentId, item?.status]);

  const save = async () => {
    if (!item) return;
    const values = await form.validateFields();
    try {
      const result = await contentApi.update(item.id, values);
      setItem(result.data);
      onUpdated?.(result.data);
      setEditing(false);
      message.success("内容已保存");
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "保存失败");
    }
  };

  const remove = async () => {
    if (!item) return;
    try {
      await contentApi.remove(item.id);
      message.success("内容已移除");
      onDeleted(item.id);
      onClose();
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "删除失败");
    }
  };

  const findSimilar = async () => {
    if (!item) return;
    setMergeOpen(true);
    setMergeLoading(true);
    setMergePreview(null);
    try {
      const result = await mergeApi.similar(item.id);
      setSimilar(result.data);
      setSelectedSimilar([]);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "相似内容检测失败");
    } finally {
      setMergeLoading(false);
    }
  };

  const previewMerge = async () => {
    if (!item || selectedSimilar.length === 0) return;
    setMergeLoading(true);
    try {
      const result = await mergeApi.preview(item.id, selectedSimilar);
      setMergePreview(result.data);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "合并预览失败");
    } finally {
      setMergeLoading(false);
    }
  };

  const confirmMerge = async () => {
    if (!item || selectedSimilar.length === 0) return;
    setMergeLoading(true);
    try {
      const result = await mergeApi.merge(item.id, selectedSimilar);
      setItem(result.data);
      onUpdated?.(result.data);
      setMergeOpen(false);
      message.success(`已合并 ${selectedSimilar.length + 1} 条内容`);
      await load(result.data.id);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "合并失败");
    } finally {
      setMergeLoading(false);
    }
  };

  const savePoint = async (pointId: string) => {
    try {
      const result = await knowledgeApi.updatePoint(pointId, pointDraft);
      setPoints((current) =>
        current.map((point) => (point.id === pointId ? result.data : point)),
      );
      setEditingPointId(null);
      message.success("知识点已更新");
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "知识点保存失败");
    }
  };

  const removePoint = async (pointId: string) => {
    try {
      await knowledgeApi.removePoint(pointId);
      setPoints((current) => current.filter((point) => point.id !== pointId));
      message.success("知识点已删除");
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "知识点删除失败");
    }
  };

  const meta = item ? sourceMeta[item.source_type] || sourceMeta.text : null;
  const visibleReprocessState: ReprocessState =
    reprocessState !== "idle"
      ? reprocessState
      : item?.status === "pending"
        ? "running"
        : item?.status === "finalizing"
          ? "running"
          : item?.status === "cancelled"
            ? "cancelled"
        : item?.status === "failed"
          ? "error"
          : "idle";
  const isReprocessing =
    visibleReprocessState === "starting" ||
    visibleReprocessState === "running" ||
    visibleReprocessState === "cancelling";
  const canCancel = item?.status === "pending";

  return (
    <>
      <Drawer
        open={Boolean(contentId)}
        onClose={onClose}
        afterOpenChange={(isOpen) => {
          if (isOpen && contentId) void load(contentId);
          if (!isOpen) {
            setItem(null);
            setEditing(false);
            setReprocessState("idle");
            setReprocessMessage("");
            if (successTimerRef.current !== null) {
              window.clearTimeout(successTimerRef.current);
              successTimerRef.current = null;
            }
          }
        }}
        width={720}
        title={null}
        className="detail-drawer"
        extra={
          item && (
            <div className="detail-actions">
              {editing ? (
                <>
                  <Button onClick={() => setEditing(false)}>取消</Button>
                  <Button type="primary" icon={<SaveOutlined />} onClick={save}>保存</Button>
                </>
              ) : (
                <>
                  <Button
                    icon={<MergeCellsOutlined />}
                    disabled={isReprocessing}
                    onClick={findSimilar}
                  >
                    检测相似
                  </Button>
                  <Button
                    icon={<EditOutlined />}
                    disabled={isReprocessing}
                    onClick={() => {
                      setEditing(true);
                      window.setTimeout(() => {
                        form.setFieldsValue({
                          title: item.title,
                          summary: item.summary,
                          original_text: item.original_text,
                        });
                      }, 0);
                    }}
                  >
                    编辑
                  </Button>
                  {isReprocessing ? (
                    <Popconfirm
                      title="停止这次整理？"
                      description="系统会放弃本次未完成的结果，已经保存的摘要和知识点不会改变。"
                      okText="停止整理"
                      cancelText="继续整理"
                      okButtonProps={{ danger: true }}
                      disabled={!canCancel || reprocessState === "cancelling"}
                      onConfirm={cancelProcessing}
                    >
                      <Button
                        danger
                        className="reprocess-cancel"
                        icon={<StopOutlined />}
                        loading={reprocessState === "cancelling"}
                        disabled={!canCancel || reprocessState === "cancelling"}
                        aria-label={canCancel ? "停止整理" : "正在写入整理结果"}
                        title={canCancel ? "停止整理" : "正在写入整理结果"}
                      >
                        {reprocessState === "cancelling"
                          ? "正在停止"
                          : canCancel
                            ? "停止整理"
                            : item.status === "finalizing"
                              ? "正在写入"
                              : "正在启动"}
                      </Button>
                    </Popconfirm>
                  ) : (
                    <Popconfirm
                      title="重新整理这条内容？"
                      description="系统会重新提纯原文，并替换当前 AI 摘要和自动生成的知识点。原始内容不会改变。"
                      okText="开始整理"
                      cancelText="取消"
                      onConfirm={processAgain}
                    >
                      <Button
                        className="reprocess-trigger"
                        data-state={visibleReprocessState}
                        icon={
                          visibleReprocessState === "success" ? (
                            <CheckCircleOutlined />
                          ) : visibleReprocessState === "error" ? (
                            <ExclamationCircleOutlined />
                          ) : (
                            <ReloadOutlined />
                          )
                        }
                      >
                        {visibleReprocessState === "success"
                          ? "已整理"
                          : visibleReprocessState === "error"
                            ? "再次整理"
                            : "重新整理"}
                      </Button>
                    </Popconfirm>
                  )}
                  <Popconfirm
                    title="删除这条内容？"
                    description="关联的知识点也会一起删除，此操作无法撤销。"
                    okText="删除"
                    cancelText="保留"
                    okButtonProps={{ danger: true }}
                    onConfirm={remove}
                  >
                    <Button danger type="text" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </>
              )}
            </div>
          )
        }
      >
        {loading ? (
          <Skeleton active paragraph={{ rows: 10 }} />
        ) : item ? (
          <article className="content-detail">
            <div className="detail-meta-row">
              <Tag bordered={false} className={`source-tag ${meta?.className}`}>
                {meta?.label}
              </Tag>
              <span>{formatFullDate(item.created_at)}</span>
              {item.status === "pending" && <Tag color="processing">整理中</Tag>}
              {item.status === "finalizing" && <Tag color="processing">正在写入</Tag>}
              {item.status === "cancelled" && <Tag>已停止</Tag>}
              {item.status === "failed" && <Tag color="error">整理失败</Tag>}
              {item.status === "processed" && item.distilled_text === null && (
                <Tag color="warning">旧内容需重新整理后参与检索</Tag>
              )}
            </div>

            {visibleReprocessState !== "idle" && (
              <ReprocessStatus
                state={visibleReprocessState}
                message={reprocessMessage}
                onRetry={processAgain}
              />
            )}

            {editing ? (
              <Form form={form} layout="vertical" className="content-edit-form">
                <Form.Item name="title" label="标题" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="summary" label="内容摘要">
                  <Input.TextArea autoSize={{ minRows: 4, maxRows: 10 }} />
                </Form.Item>
                <Form.Item name="original_text" label="原始内容" rules={[{ required: true }]}>
                  <Input.TextArea autoSize={{ minRows: 12, maxRows: 24 }} />
                </Form.Item>
              </Form>
            ) : (
              <>
                <Typography.Title>{item.title}</Typography.Title>
                {item.source_url && (
                  <a href={item.source_url} target="_blank" rel="noreferrer" className="source-link">
                    <LinkOutlined /> 查看原始链接
                  </a>
                )}
                <section className="summary-panel">
                  <div className="section-label"><StarOutlined /> AI 摘要</div>
                  {item.summary ? (
                    <Typography.Paragraph>{item.summary}</Typography.Paragraph>
                  ) : item.status === "failed" || item.status === "cancelled" ? (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        item.status === "cancelled"
                          ? "整理已停止，可以随时重新开始"
                          : "这次整理没有完成，可以稍后重新尝试"
                      }
                    />
                  ) : (
                    <div className="summary-thinking"><span className="thinking-pulse" />AI 正在阅读和提炼这条内容…</div>
                  )}
                </section>

                {item.distilled_text !== null && item.distilled_text !== undefined && (
                  <Collapse
                    ghost
                    className="original-collapse"
                    items={[
                      {
                        key: "distilled",
                        label: "查看 AI 提纯后的知识正文",
                        children: item.distilled_text ? (
                          <Typography.Paragraph className="original-text">
                            {item.distilled_text}
                          </Typography.Paragraph>
                        ) : (
                          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="这份材料没有识别出可沉淀的知识内容" />
                        ),
                      },
                    ]}
                  />
                )}

                <section className="point-section">
                  <div className="point-section-heading">
                    <span><BranchesOutlined /> 知识点</span>
                    <small>{points.length} 条</small>
                  </div>
                  {points.length ? (
                    <div className="point-list">
                      {points.map((point) => (
                        <article key={point.id}>
                          {editingPointId === point.id ? (
                            <div className="point-editor">
                              <Input
                                value={pointDraft.title}
                                onChange={(event) =>
                                  setPointDraft((draft) => ({ ...draft, title: event.target.value }))
                                }
                              />
                              <Input.TextArea
                                value={pointDraft.content}
                                autoSize={{ minRows: 2, maxRows: 6 }}
                                onChange={(event) =>
                                  setPointDraft((draft) => ({ ...draft, content: event.target.value }))
                                }
                              />
                              <span>
                                <Button size="small" onClick={() => setEditingPointId(null)}>取消</Button>
                                <Button size="small" type="primary" onClick={() => savePoint(point.id)}>保存</Button>
                              </span>
                            </div>
                          ) : (
                            <>
                              <div>
                                <strong>{point.title}</strong>
                                <span className="point-actions">
                                  {point.category && <Tag bordered={false}>{point.category}</Tag>}
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={<EditOutlined />}
                                    onClick={() => {
                                      setEditingPointId(point.id);
                                      setPointDraft({ title: point.title, content: point.content });
                                    }}
                                  />
                                  <Popconfirm
                                    title="删除这个知识点？"
                                    okText="删除"
                                    cancelText="保留"
                                    onConfirm={() => removePoint(point.id)}
                                  >
                                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                                  </Popconfirm>
                                </span>
                              </div>
                              <p>{point.content}</p>
                            </>
                          )}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="point-empty">整理完成后，知识点会出现在这里。</div>
                  )}
                </section>

                {item.extracted_knowledge &&
                  Object.entries(item.extracted_knowledge).some(
                    ([key]) => key !== "summary",
                  ) && (
                    <section className="custom-result-section">
                      <div className="point-section-heading">
                        <span><StarOutlined /> 模板字段</span>
                      </div>
                      <div className="custom-result-grid">
                        {Object.entries(item.extracted_knowledge)
                          .filter(([key]) => key !== "summary" && key !== "distillation")
                          .map(([key, value]) => (
                            <article key={key}>
                              <strong>{key}</strong>
                              <p>
                                {Array.isArray(value)
                                  ? value.join("；")
                                  : typeof value === "object"
                                  ? JSON.stringify(value, null, 2)
                                  : String(value)}
                              </p>
                            </article>
                          ))}
                      </div>
                    </section>
                  )}

                <Collapse
                  ghost
                  className="original-collapse"
                  items={[
                    {
                      key: "original",
                      label: "展开原始内容",
                      children: <Typography.Paragraph className="original-text">{item.original_text}</Typography.Paragraph>,
                    },
                  ]}
                />
              </>
            )}
          </article>
        ) : (
          <Empty description="没有找到这条内容" />
        )}
      </Drawer>

      <Modal
        open={mergeOpen}
        title="相似内容与合并"
        onCancel={() => setMergeOpen(false)}
        width={720}
        destroyOnHidden
        footer={
          mergePreview
            ? [
                <Button key="back" onClick={() => setMergePreview(null)}>返回选择</Button>,
                <Button key="merge" type="primary" loading={mergeLoading} onClick={confirmMerge}>确认合并</Button>,
              ]
            : [
                <Button key="cancel" onClick={() => setMergeOpen(false)}>取消</Button>,
                <Button
                  key="preview"
                  type="primary"
                  disabled={selectedSimilar.length === 0}
                  loading={mergeLoading}
                  onClick={previewMerge}
                >
                  预览合并
                </Button>,
              ]
        }
      >
        {mergeLoading && !similar.length ? (
          <Skeleton active paragraph={{ rows: 5 }} />
        ) : mergePreview ? (
          <div className="merge-preview">
            <div className="merge-preview-mark"><MergeCellsOutlined /></div>
            <Typography.Title level={4}>{mergePreview.merged_title}</Typography.Title>
            <Typography.Paragraph>{mergePreview.merged_summary}</Typography.Paragraph>
            {mergePreview.conflicts.length > 0 && (
              <Tag color="warning">发现 {mergePreview.conflicts.length} 处内容差异，已同时保留</Tag>
            )}
            <Collapse
              ghost
              items={[{
                key: "merged",
                label: "查看合并后的完整内容",
                children: <Typography.Paragraph className="original-text">{mergePreview.merged_text}</Typography.Paragraph>,
              }]}
            />
          </div>
        ) : similar.length ? (
          <Checkbox.Group
            value={selectedSimilar}
            onChange={(values) => setSelectedSimilar(values as string[])}
            className="similar-list"
          >
            {similar.map((candidate) => (
              <label key={candidate.id}>
                <Checkbox value={candidate.id} />
                <div>
                  <strong>{candidate.title}</strong>
                  <p>{candidate.summary || "暂无摘要"}</p>
                  <Progress percent={Math.round(candidate.similarity * 100)} size="small" showInfo={false} />
                </div>
                <Tag bordered={false}>{Math.round(candidate.similarity * 100)}%</Tag>
              </label>
            ))}
          </Checkbox.Group>
        ) : (
          <Empty description="没有发现需要合并的相似内容" />
        )}
      </Modal>
    </>
  );
}

function ReprocessStatus({
  state,
  message,
  onRetry,
}: {
  state: Exclude<ReprocessState, "idle">;
  message: string;
  onRetry: () => void;
}) {
  const isBusy =
    state === "starting" || state === "running" || state === "cancelling";
  const content = {
    starting: {
      title: "正在提交整理任务",
      description: "任务启动后会在后台运行，当前内容会保留到新结果写入完成。",
    },
    running: {
      title: "AI 正在重新整理",
      description: "系统会先过滤无关信息，再重建摘要、知识点和检索索引；需要时可以停止。",
    },
    cancelling: {
      title: "正在停止整理",
      description: "正在通知后台终止任务，未完成的结果不会写入知识库。",
    },
    cancelled: {
      title: "整理已停止",
      description: "未完成的结果没有写入，原有摘要和知识点保持不变。",
    },
    success: {
      title: "重新整理完成",
      description: "页面已更新为新的提纯正文、摘要和知识点。",
    },
    error: {
      title: "重新整理未完成",
      description: "任务已停止，当前可见内容不会被未完成的结果覆盖。",
    },
  }[state];

  return (
    <section
      className={`reprocess-status reprocess-status--${state}`}
      role="status"
      aria-live="polite"
      aria-busy={isBusy}
    >
      <span className="reprocess-status__icon" aria-hidden="true">
        {isBusy ? (
          <LoadingOutlined spin />
        ) : state === "success" ? (
          <CheckCircleOutlined />
        ) : state === "cancelled" ? (
          <StopOutlined />
        ) : (
          <ExclamationCircleOutlined />
        )}
      </span>
      <div className="reprocess-status__copy">
        <strong>{content.title}</strong>
        <p>{message || content.description}</p>
        {(state === "starting" || state === "running") && (
          <div className="reprocess-stages" aria-label="整理步骤">
            <span>提纯正文</span>
            <span>重建摘要与知识点</span>
            <span>更新检索索引</span>
          </div>
        )}
      </div>
      {(state === "error" || state === "cancelled") && (
        <Button className="reprocess-status__retry" onClick={onRetry}>
          再次尝试
        </Button>
      )}
    </section>
  );
}
