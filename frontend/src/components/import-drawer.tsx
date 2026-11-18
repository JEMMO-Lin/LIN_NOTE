"use client";

import { useRef, useState } from "react";
import {
  CopyOutlined,
  FileImageOutlined,
  LinkOutlined,
  LoadingOutlined,
  ReadOutlined,
  StarOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Drawer,
  Form,
  Input,
  Segmented,
  Select,
  Typography,
  Upload,
} from "antd";
import type { UploadFile } from "antd";

import { ApiError, contentApi, templateApi } from "@/services/api";
import type { ContentItem, KnowledgeBase, SummaryTemplate } from "@/types";
import { createBrowserCollectorBookmarklet } from "@/utils/browser-capture";

type ImportMode = "text" | "url" | "image" | "browser";
type ImportFeedback = {
  type: "error" | "warning";
  message: string;
  description?: string;
};

const MAX_IMAGE_COUNT = 10;
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;
const SUPPORTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "导入失败，请稍后重试";
}

function isSupportedImage(file: File) {
  return (
    SUPPORTED_IMAGE_TYPES.has(file.type) ||
    /\.(png|jpe?g|webp)$/i.test(file.name)
  );
}

type Props = {
  open: boolean;
  knowledgeBase: KnowledgeBase | null;
  onClose: () => void;
  onImported: (item: ContentItem) => void;
};

export function ImportDrawer({
  open,
  knowledgeBase,
  onClose,
  onImported,
}: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [mode, setMode] = useState<ImportMode>("text");
  const [loading, setLoading] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [templates, setTemplates] = useState<SummaryTemplate[]>([]);
  const [feedback, setFeedback] = useState<ImportFeedback | null>(null);
  const [imageProgress, setImageProgress] = useState<{
    current: number;
    total: number;
  } | null>(null);
  const [bookmarklet, setBookmarklet] = useState("");
  const bookmarkletRef = useRef<HTMLAnchorElement>(null);

  const reset = () => {
    form.resetFields();
    setFileList([]);
    setMode("text");
    setFeedback(null);
    setImageProgress(null);
  };

  const loadTemplates = async () => {
    try {
      const result = await templateApi.list();
      setTemplates(result.data);
      const defaultTemplate = result.data.find((item) => item.is_default);
      if (defaultTemplate) {
        form.setFieldsValue({
          template_id: defaultTemplate.id,
          summary_style: defaultTemplate.default_style,
        });
      } else {
        form.setFieldValue("summary_style", "medium");
      }
    } catch {
      form.setFieldValue("summary_style", "medium");
    }
  };

  const submit = async () => {
    if (mode === "browser") {
      window.open("/capture", "_blank", "noopener,noreferrer");
      return;
    }
    if (!knowledgeBase) {
      message.info("请先创建一个知识库");
      return;
    }
    setFeedback(null);
    setLoading(true);
    try {
      if (mode === "text") {
        const values = await form.validateFields([
          "title",
          "text",
          "summary_style",
          "template_id",
        ]);
        const result = await contentApi.importText({
          kb_id: knowledgeBase.id,
          title: values.title?.trim() || undefined,
          text: values.text.trim(),
          summary_style: values.summary_style || "medium",
          template_id: values.template_id || undefined,
        });
        onImported(result.data);
      } else if (mode === "url") {
        const values = await form.validateFields(["url"]);
        const result = await contentApi.importUrl({
          kb_id: knowledgeBase.id,
          url: values.url.trim(),
        });
        onImported(result.data);
      } else {
        const selectedFiles = fileList.filter(
          (item): item is UploadFile & { originFileObj: File } =>
            Boolean(item.originFileObj),
        );
        if (!selectedFiles.length) {
          setFeedback({
            type: "error",
            message: "请先选择至少一张图片",
          });
          return;
        }

        const imported: ContentItem[] = [];
        const failed: Array<{ file: UploadFile; reason: string }> = [];
        for (const [index, uploadFile] of selectedFiles.entries()) {
          setImageProgress({ current: index + 1, total: selectedFiles.length });
          try {
            const result = await contentApi.importImage(
              knowledgeBase.id,
              uploadFile.originFileObj,
            );
            imported.push(result.data);
          } catch (error) {
            failed.push({ file: uploadFile, reason: errorMessage(error) });
          }
        }

        imported.forEach(onImported);
        if (failed.length) {
          setFileList(
            failed.map(({ file, reason }) => ({
              ...file,
              status: "error",
              error: new Error(reason),
            })),
          );
          setFeedback({
            type: imported.length ? "warning" : "error",
            message: imported.length
              ? `已导入 ${imported.length} 张，${failed.length} 张失败`
              : `${failed.length} 张图片均未导入`,
            description: `${failed[0].file.name}：${failed[0].reason}${
              failed.length > 1 ? "。失败图片已保留，可直接重试。" : ""
            }`,
          });
          if (imported.length) {
            message.success(`已成功导入 ${imported.length} 张图片`);
          }
          return;
        }

        message.success(
          selectedFiles.length === 1
            ? "图片已收进来，AI 正在整理"
            : `${selectedFiles.length} 张图片已收进来，AI 正在整理`,
        );
        reset();
        onClose();
        return;
      }

      message.success("内容已收进来，AI 正在整理");
      reset();
      onClose();
    } catch (error) {
      if ((error as { errorFields?: unknown }).errorFields) return;
      setFeedback({
        type: "error",
        message: mode === "url" ? "链接导入失败" : "内容导入失败",
        description: errorMessage(error),
      });
    } finally {
      setLoading(false);
      setImageProgress(null);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={() => {
        if (loading) return;
        reset();
        onClose();
      }}
      afterOpenChange={(isOpen) => {
        if (isOpen) void loadTemplates();
        else reset();
      }}
      width={560}
      title={null}
      className="import-drawer"
      closable={!loading}
      keyboard={!loading}
      maskClosable={!loading}
      footer={
        <div className="drawer-footer">
          <div className="ai-hint">
            <StarOutlined />
            <span>保存后会自动生成摘要与知识点</span>
          </div>
          <Button
            type="primary"
            size="large"
            loading={loading}
            onClick={submit}
            icon={
              loading ? (
                <LoadingOutlined />
              ) : mode === "browser" ? (
                <ReadOutlined />
              ) : (
                <StarOutlined />
              )
            }
          >
            {loading && imageProgress
              ? `正在识别 ${imageProgress.current}/${imageProgress.total}`
              : mode === "browser"
                ? "打开采集接收页"
                : "开始整理"}
          </Button>
        </div>
      }
    >
      <div className="drawer-heading">
        <span className="eyebrow">ADD TO YOUR SPACE</span>
        <Typography.Title level={2}>收进一条新内容</Typography.Title>
        <Typography.Paragraph>
          将保存到「{knowledgeBase?.name || "尚未选择知识库"}」，整理完成后即可搜索和回看。
        </Typography.Paragraph>
      </div>

      <Segmented
        block
        value={mode}
        onChange={(value) => {
          setMode(value as ImportMode);
          setFeedback(null);
          if (value === "browser") {
            setBookmarklet(
              createBrowserCollectorBookmarklet(
                `${window.location.origin}/capture`,
              ),
            );
          }
        }}
        options={[
          { label: "粘贴文本", value: "text" },
          { label: "导入链接", value: "url" },
          { label: "识别图片", value: "image" },
          { label: "浏览器采集", value: "browser" },
        ]}
      />

      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        className="import-form"
        onValuesChange={() => setFeedback(null)}
      >
        {feedback && (
          <Alert
            className="import-feedback"
            type={feedback.type}
            message={feedback.message}
            description={feedback.description}
            showIcon
            closable
            onClose={() => setFeedback(null)}
          />
        )}
        {mode === "text" && (
          <>
            <div className="summary-options">
              <Form.Item name="summary_style" label="整理详略" initialValue="medium">
                <Segmented
                  block
                  options={[
                    { label: "简明", value: "brief" },
                    { label: "中等", value: "medium" },
                    { label: "详细", value: "detailed" },
                  ]}
                />
              </Form.Item>
              <Form.Item name="template_id" label="总结模板">
                <Select
                  allowClear
                  placeholder="使用系统默认结构"
                  options={templates.map((item) => ({
                    value: item.id,
                    label: item.name,
                  }))}
                  onChange={(id) => {
                    const selected = templates.find((item) => item.id === id);
                    if (selected) {
                      form.setFieldValue("summary_style", selected.default_style);
                    }
                  }}
                />
              </Form.Item>
            </div>
            <Form.Item name="title" label="标题（可选）">
              <Input placeholder="不填写时会自动生成标题" />
            </Form.Item>
            <Form.Item
              name="text"
              label="内容"
              rules={[{ required: true, message: "粘贴或输入一些内容吧" }]}
            >
              <Input.TextArea
                placeholder="一段文章、课堂笔记、会议记录，或刚刚冒出来的想法……"
                autoSize={{ minRows: 12, maxRows: 20 }}
                showCount
              />
            </Form.Item>
          </>
        )}

        {mode === "url" && (
          <div className="import-mode-panel">
            <div className="mode-illustration mode-link">
              <LinkOutlined />
            </div>
            <Typography.Title level={4}>把值得留下的链接交给 KnowFlow</Typography.Title>
            <Typography.Paragraph type="secondary">
              支持常见网页内容。若平台限制读取，系统会提示你改用文本方式。
            </Typography.Paragraph>
            <Form.Item
              name="url"
              rules={[
                { required: true, message: "请粘贴链接" },
                { type: "url", message: "请输入完整的网址" },
              ]}
            >
              <Input
                prefix={<LinkOutlined />}
                placeholder="https://..."
                size="large"
              />
            </Form.Item>
          </div>
        )}

        {mode === "image" && (
          <div className="import-mode-panel">
            <div className="mode-illustration mode-image">
              <FileImageOutlined />
            </div>
            <Typography.Title level={4}>从截图里提取知识</Typography.Title>
            <Typography.Paragraph type="secondary">
              适合课件、书页、聊天截图和无法复制的内容。
            </Typography.Paragraph>
            <Upload.Dragger
              accept="image/png,image/jpeg,image/webp"
              multiple
              maxCount={MAX_IMAGE_COUNT}
              fileList={fileList}
              beforeUpload={(file) => {
                if (!isSupportedImage(file)) {
                  setFeedback({
                    type: "error",
                    message: `${file.name} 不是支持的图片格式`,
                    description: "请选择 PNG、JPG、JPEG 或 WEBP 图片。",
                  });
                  return Upload.LIST_IGNORE;
                }
                if (file.size > MAX_IMAGE_SIZE) {
                  setFeedback({
                    type: "error",
                    message: `${file.name} 超过 10 MB`,
                    description: "请压缩图片后再试。",
                  });
                  return Upload.LIST_IGNORE;
                }
                setFeedback(null);
                return false;
              }}
              onChange={({ fileList: next }) => {
                setFileList(next.slice(0, MAX_IMAGE_COUNT));
              }}
            >
              <p className="ant-upload-drag-icon"><UploadOutlined /></p>
              <p className="ant-upload-text">拖到这里，或点击选择多张图片</p>
              <p className="ant-upload-hint">
                一次最多 {MAX_IMAGE_COUNT} 张，支持 PNG、JPG、WEBP，单张不超过 10 MB
              </p>
            </Upload.Dragger>
          </div>
        )}

        {mode === "browser" && (
          <div className="import-mode-panel browser-capture-install">
            <div className="mode-illustration mode-browser">
              <ReadOutlined />
            </div>
            <Typography.Title level={4}>从已登录的网页采集内容</Typography.Title>
            <Typography.Paragraph type="secondary">
              适合小红书等限制服务端读取的平台。采集前会让你检查正文、图片和字幕，不会把登录 Cookie 交给 KnowFlow。
            </Typography.Paragraph>

            <div className="bookmarklet-install-card">
              <strong>安装一次，以后随处使用</strong>
              <ol>
                <li>显示浏览器书签栏。</li>
                <li>把下面的按钮拖到书签栏。</li>
                <li>打开要保存的网页，点击这个书签。</li>
              </ol>
              <a
                ref={(element) => {
                  bookmarkletRef.current = element;
                  // React sanitizes javascript: URLs in JSX. This is a
                  // user-installed bookmarklet, so set it on the DOM node.
                  if (element && bookmarklet) {
                    element.setAttribute("href", bookmarklet);
                  }
                }}
                className="bookmarklet-button"
                draggable
                onClick={(event) => event.preventDefault()}
              >
                <ReadOutlined /> 保存到 KnowFlow
              </a>
              <Button
                icon={<CopyOutlined />}
                disabled={!bookmarklet}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(bookmarklet);
                    message.success("采集助手代码已复制，可粘贴为书签网址");
                  } catch {
                    setFeedback({
                      type: "error",
                      message: "无法复制采集助手代码",
                      description: "请直接把“保存到 KnowFlow”按钮拖到书签栏。",
                    });
                  }
                }}
              >
                复制书签网址
              </Button>
            </div>

            <Alert
              type="info"
              showIcon
              message="多图与视频的处理范围"
              description="多图会逐张 OCR 并合并为一条内容；视频会采集标题、文案、封面及网页已有字幕。页面没有字幕时暂不转写音轨，并会在导入前明确提示。"
            />
          </div>
        )}
      </Form>
    </Drawer>
  );
}
