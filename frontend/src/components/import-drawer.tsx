"use client";

import { useState } from "react";
import {
  FileImageOutlined,
  LinkOutlined,
  LoadingOutlined,
  StarOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
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

type ImportMode = "text" | "url" | "image";

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

  const reset = () => {
    form.resetFields();
    setFileList([]);
    setMode("text");
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
    if (!knowledgeBase) {
      message.info("请先创建一个知识库");
      return;
    }
    setLoading(true);
    try {
      let result;
      if (mode === "text") {
        const values = await form.validateFields([
          "title",
          "text",
          "summary_style",
          "template_id",
        ]);
        result = await contentApi.importText({
          kb_id: knowledgeBase.id,
          title: values.title?.trim() || undefined,
          text: values.text.trim(),
          summary_style: values.summary_style || "medium",
          template_id: values.template_id || undefined,
        });
      } else if (mode === "url") {
        const values = await form.validateFields(["url"]);
        result = await contentApi.importUrl({
          kb_id: knowledgeBase.id,
          url: values.url.trim(),
        });
      } else {
        const file = fileList[0]?.originFileObj;
        if (!file) {
          message.info("先选择一张图片");
          return;
        }
        result = await contentApi.importImage(knowledgeBase.id, file);
      }

      message.success("内容已收进来，AI 正在整理");
      onImported(result.data);
      reset();
      onClose();
    } catch (error) {
      if ((error as { errorFields?: unknown }).errorFields) return;
      message.error(error instanceof ApiError ? error.message : "导入失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={() => {
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
            icon={loading ? <LoadingOutlined /> : <StarOutlined />}
          >
            开始整理
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
        onChange={(value) => setMode(value as ImportMode)}
        options={[
          { label: "粘贴文本", value: "text" },
          { label: "导入链接", value: "url" },
          { label: "识别图片", value: "image" },
        ]}
      />

      <Form form={form} layout="vertical" requiredMark={false} className="import-form">
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
              maxCount={1}
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: next }) => setFileList(next.slice(-1))}
            >
              <p className="ant-upload-drag-icon"><UploadOutlined /></p>
              <p className="ant-upload-text">拖到这里，或点击选择图片</p>
              <p className="ant-upload-hint">支持 PNG、JPG、WEBP</p>
            </Upload.Dragger>
          </div>
        )}
      </Form>
    </Drawer>
  );
}
