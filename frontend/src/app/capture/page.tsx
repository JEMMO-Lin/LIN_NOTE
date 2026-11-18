"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  FileImageOutlined,
  ImportOutlined,
  LinkOutlined,
  LoginOutlined,
  ReadOutlined,
  VideoCameraOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";

import { ApiError, contentApi, knowledgeBaseApi } from "@/services/api";
import { useAppStore } from "@/stores/app-store";
import type { ContentItem, KnowledgeBase } from "@/types";
import {
  decodeCaptureFragment,
  parseCaptureText,
  type BrowserCapturePayload,
} from "@/utils/browser-capture";

const { TextArea } = Input;

export default function BrowserCapturePage() {
  const router = useRouter();
  const { message } = App.useApp();
  const hydrated = useAppStore((state) => state.hydrated);
  const token = useAppStore((state) => state.token);
  const activeKnowledgeBaseId = useAppStore(
    (state) => state.activeKnowledgeBaseId,
  );
  const [payload, setPayload] = useState<BrowserCapturePayload | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<string>();
  const [manualPayload, setManualPayload] = useState("");
  const [loadingBases, setLoadingBases] = useState(true);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [imported, setImported] = useState<ContentItem | null>(null);

  const pageTypeLabel = useMemo(
    () =>
      payload?.page_type === "video"
        ? "视频页面"
        : payload?.page_type === "image"
          ? "多图页面"
          : "文章页面",
    [payload?.page_type],
  );

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      const fragment = new URLSearchParams(window.location.hash.slice(1)).get(
        "capture",
      );
      if (!fragment) return;
      try {
        setPayload(decodeCaptureFragment(fragment));
        setError("");
      } catch {
        setError("采集数据已损坏，请回到原网页重新点击采集助手");
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hydrated || !token) return;
    knowledgeBaseApi
      .list()
      .then((result) => {
        setKnowledgeBases(result.data);
        setKnowledgeBaseId(
          (activeKnowledgeBaseId &&
            result.data.some((item) => item.id === activeKnowledgeBaseId) &&
            activeKnowledgeBaseId) ||
            result.data[0]?.id,
        );
      })
      .catch((reason) =>
        setError(reason instanceof ApiError ? reason.message : "知识库加载失败"),
      )
      .finally(() => setLoadingBases(false));
  }, [activeKnowledgeBaseId, hydrated, token]);

  const readClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      const captured = parseCaptureText(text);
      setPayload(captured);
      setManualPayload("");
      setError("");
    } catch {
      setError("无法读取采集数据，请允许剪贴板访问，或把采集数据粘贴到下方");
    }
  };

  const parseManualPayload = () => {
    try {
      setPayload(parseCaptureText(manualPayload));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采集数据格式无效");
    }
  };

  const importCapture = async () => {
    if (!payload || !knowledgeBaseId) return;
    setImporting(true);
    setError("");
    try {
      const result = await contentApi.importBrowserCapture(
        knowledgeBaseId,
        payload,
      );
      setImported(result.data);
      window.history.replaceState(null, "", "/capture");
      message.success("网页内容已收进知识库，AI 正在整理");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "浏览器采集导入失败");
    } finally {
      setImporting(false);
    }
  };

  if (!hydrated) {
    return (
      <main className="capture-page capture-page-centered">
        <Spin size="large" />
      </main>
    );
  }

  return (
    <main className="capture-page">
      <div className="capture-shell">
        <div className="capture-brand">
          <span className="brand-mark"><ReadOutlined /></span>
          <div>
            <strong>KnowFlow 浏览器采集</strong>
            <span>在保存前确认网页正文和媒体范围</span>
          </div>
        </div>

        {error && (
          <Alert
            type="error"
            showIcon
            closable
            message={error}
            onClose={() => setError("")}
          />
        )}

        {!token ? (
          <Card className="capture-empty-card">
            <LoginOutlined className="capture-empty-icon" />
            <Typography.Title level={3}>先登录 KnowFlow</Typography.Title>
            <Typography.Paragraph type="secondary">
              采集数据仍保留在当前页面。请在新标签页登录，然后回来刷新本页。
            </Typography.Paragraph>
            <Button
              type="primary"
              icon={<LoginOutlined />}
              onClick={() => window.open("/login", "_blank")}
            >
              打开登录页
            </Button>
          </Card>
        ) : imported ? (
          <Card className="capture-success-card">
            <CheckCircleFilled className="capture-success-icon" />
            <Typography.Title level={3}>已经保存到知识库</Typography.Title>
            <Typography.Paragraph type="secondary">
              「{imported.title}」正在进行提纯、摘要和知识点提取。
            </Typography.Paragraph>
            <Space wrap>
              <Button type="primary" onClick={() => router.push("/")}>
                返回知识空间
              </Button>
              <Button
                onClick={() => {
                  setImported(null);
                  setPayload(null);
                }}
              >
                继续采集
              </Button>
            </Space>
          </Card>
        ) : payload ? (
          <div className="capture-grid">
            <Card className="capture-preview-card">
              <div className="capture-preview-heading">
                <div>
                  <span className="eyebrow">CAPTURE PREVIEW</span>
                  <Typography.Title level={3}>检查后再导入</Typography.Title>
                </div>
                <Space wrap>
                  <Tag
                    icon={
                      payload.page_type === "video" ? (
                        <VideoCameraOutlined />
                      ) : payload.page_type === "image" ? (
                        <FileImageOutlined />
                      ) : (
                        <ReadOutlined />
                      )
                    }
                  >
                    {pageTypeLabel}
                  </Tag>
                  {payload.image_urls.length > 0 && (
                    <Tag>{payload.image_urls.length} 张图片</Tag>
                  )}
                  {payload.subtitle_text && <Tag color="green">已读取字幕</Tag>}
                </Space>
              </div>

              {payload.page_type === "video" && !payload.subtitle_text && (
                <Alert
                  type="warning"
                  showIcon
                  message="页面没有提供可读取字幕"
                  description="将导入标题、发布文案和封面图片；不会把视频音轨误标为已转写。"
                />
              )}

              <label className="capture-field">
                <span>标题</span>
                <Input
                  value={payload.title}
                  onChange={(event) =>
                    setPayload({ ...payload, title: event.target.value })
                  }
                />
              </label>
              <label className="capture-field">
                <span>原始链接</span>
                <Input value={payload.url} prefix={<LinkOutlined />} readOnly />
              </label>
              <label className="capture-field">
                <span>网页正文</span>
                <TextArea
                  value={payload.text}
                  autoSize={{ minRows: 10, maxRows: 20 }}
                  onChange={(event) =>
                    setPayload({ ...payload, text: event.target.value })
                  }
                />
              </label>
            </Card>

            <Card className="capture-action-card">
              <Typography.Title level={4}>保存设置</Typography.Title>
              <Typography.Text type="secondary">
                多张图片会逐张 OCR，并与网页正文合并成同一条内容。
              </Typography.Text>
              <label className="capture-field">
                <span>目标知识库</span>
                <Select
                  loading={loadingBases}
                  value={knowledgeBaseId}
                  onChange={setKnowledgeBaseId}
                  options={knowledgeBases.map((item) => ({
                    value: item.id,
                    label: item.name,
                  }))}
                  placeholder="选择知识库"
                />
              </label>
              {!knowledgeBases.length && !loadingBases && (
                <Alert type="info" showIcon message="请先创建一个知识库" />
              )}
              <Button
                type="primary"
                size="large"
                block
                icon={<ImportOutlined />}
                loading={importing}
                disabled={!knowledgeBaseId}
                onClick={importCapture}
              >
                {importing ? "正在读取图片并导入" : "确认导入"}
              </Button>
              <Button
                type="text"
                block
                icon={<ArrowLeftOutlined />}
                onClick={() => setPayload(null)}
              >
                放弃这次采集
              </Button>
            </Card>
          </div>
        ) : (
          <Card className="capture-empty-card">
            <ImportOutlined className="capture-empty-icon" />
            <Typography.Title level={3}>等待网页采集数据</Typography.Title>
            <Typography.Paragraph type="secondary">
              回到要保存的网页并点击书签栏中的“保存到 KnowFlow”。若页面已经复制了采集数据，也可以在这里读取。
            </Typography.Paragraph>
            <Space wrap>
              <Button type="primary" onClick={readClipboard}>
                从剪贴板读取
              </Button>
              <Button onClick={() => router.push("/")}>返回知识空间</Button>
            </Space>
            <div className="capture-manual-input">
              <TextArea
                value={manualPayload}
                onChange={(event) => setManualPayload(event.target.value)}
                placeholder="也可以把采集助手生成的 JSON 粘贴到这里"
                autoSize={{ minRows: 4, maxRows: 8 }}
              />
              <Button disabled={!manualPayload.trim()} onClick={parseManualPayload}>
                解析采集数据
              </Button>
            </div>
          </Card>
        )}
      </div>
    </main>
  );
}
