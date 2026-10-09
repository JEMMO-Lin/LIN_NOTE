"use client";

import { useEffect, useState } from "react";
import {
  ApiOutlined,
  CheckCircleFilled,
  CloudServerOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
  DownloadOutlined,
  HistoryOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { App, Button, Form, Input, Skeleton, Tag, Typography } from "antd";

import {
  ApiError,
  authApi,
  downloadAuthenticatedFile,
  knowledgeBaseApi,
  llmApi,
  mergeApi,
} from "@/services/api";
import type { KnowledgeBase, LLMConfig, MergeHistory } from "@/types";
import { parseApiDate } from "@/utils/format";

export function SettingsView({
  onSignOut,
  knowledgeBase,
}: {
  onSignOut: () => void;
  knowledgeBase: KnowledgeBase | null;
}) {
  const { message } = App.useApp();
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<MergeHistory[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    Promise.all([
      llmApi.config(),
      authApi.me(),
      mergeApi.history(knowledgeBase?.id),
    ])
      .then(([configResult, userResult, historyResult]) => {
        setConfig(configResult.data);
        setHistory(historyResult.data);
        form.setFieldsValue({
          username: userResult.data.username,
          avatar: userResult.data.avatar,
        });
      })
      .catch((error) =>
        message.error(error instanceof ApiError ? error.message : "配置读取失败"),
      )
      .finally(() => setLoading(false));
  }, [form, knowledgeBase?.id, message]);

  const saveProfile = async () => {
    try {
      const values = await form.validateFields();
      await authApi.updateMe(values);
      message.success("个人资料已保存");
    } catch (error) {
      if ((error as { errorFields?: unknown }).errorFields) return;
      message.error(error instanceof ApiError ? error.message : "保存失败");
    }
  };

  const exportKb = async (format: "markdown" | "json") => {
    if (!knowledgeBase) {
      message.info("请先选择知识库");
      return;
    }
    try {
      await downloadAuthenticatedFile(
        knowledgeBaseApi.exportUrl(knowledgeBase.id, format),
        `${knowledgeBase.name}.${format === "markdown" ? "md" : "json"}`,
      );
      message.success("导出文件已生成");
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "导出失败");
    }
  };

  return (
    <div className="settings-view view-enter">
      <div className="settings-heading">
        <span className="eyebrow">YOUR PRIVATE SPACE</span>
        <Typography.Title>设置</Typography.Title>
        <Typography.Paragraph>
          查看当前服务连接与 AI 能力。敏感配置只保存在后端，不会发送到浏览器。
        </Typography.Paragraph>
      </div>

      <section className="settings-section">
        <div className="settings-section-title">
          <UserOutlined />
          <div>
            <strong>个人资料</strong>
            <span>用于标识这个知识空间</span>
          </div>
        </div>
        <div className="settings-card">
          <Form form={form} layout="vertical" className="profile-form">
            <Form.Item name="username" label="昵称" rules={[{ required: true }, { min: 2 }]}>
              <Input placeholder="你的名字" />
            </Form.Item>
            <Form.Item name="avatar" label="头像地址">
              <Input placeholder="https://..." />
            </Form.Item>
            <Button type="primary" onClick={saveProfile}>保存资料</Button>
          </Form>
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <ApiOutlined />
          <div>
            <strong>AI 服务</strong>
            <span>当前用于摘要、知识点提取与语义搜索的模型</span>
          </div>
        </div>
        {loading ? (
          <div className="settings-card"><Skeleton active /></div>
        ) : config ? (
          <div className="settings-card provider-card">
            <div className="provider-main">
              <span className="provider-logo"><CloudServerOutlined /></span>
              <div>
                <strong>
                  {config.available_providers.find(
                    (provider) => provider.provider === config.current_provider,
                  )?.display_name || config.current_provider}
                </strong>
                <span>{config.model_balanced || config.model_fast || "使用服务端默认模型"}</span>
              </div>
            </div>
            <Tag color="success" bordered={false} icon={<CheckCircleFilled />}>
              已配置
            </Tag>
            <div className="model-details">
              <span><small>快速任务</small>{config.model_fast || "默认"}</span>
              <span><small>深度整理</small>{config.model_quality || "默认"}</span>
              <span><small>知识检索</small>{config.embedding_model || "默认"}</span>
            </div>
          </div>
        ) : null}
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <SafetyCertificateOutlined />
          <div>
            <strong>数据与隐私</strong>
            <span>KnowFlow 适合部署在你自己的设备或私有服务中</span>
          </div>
        </div>
        <div className="privacy-grid">
          <div className="settings-card privacy-card">
            <DatabaseOutlined />
            <div><strong>私有存储</strong><span>笔记内容由你的后端数据库保存</span></div>
          </div>
          <div className="settings-card privacy-card">
            <SafetyCertificateOutlined />
            <div><strong>密钥隔离</strong><span>AI 密钥不会出现在前端和浏览器中</span></div>
          </div>
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <DownloadOutlined />
          <div>
            <strong>数据导出</strong>
            <span>将当前知识库保存为可迁移的 Markdown 或 JSON</span>
          </div>
        </div>
        <div className="settings-card export-card">
          <div>
            <strong>{knowledgeBase?.name || "尚未选择知识库"}</strong>
            <span>导出包含摘要、原文和全部知识点。</span>
          </div>
          <span>
            <Button icon={<DownloadOutlined />} onClick={() => exportKb("markdown")}>Markdown</Button>
            <Button icon={<DownloadOutlined />} onClick={() => exportKb("json")}>JSON</Button>
          </span>
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <HistoryOutlined />
          <div>
            <strong>合并历史</strong>
            <span>追溯当前知识库中的内容整理记录</span>
          </div>
        </div>
        <div className="settings-card merge-history-list">
          {history.length ? history.slice(0, 10).map((record) => (
            <div key={record.id}>
              <span className="history-mark"><HistoryOutlined /></span>
              <div>
                <strong>合并了 {record.source_titles.length + 1} 条内容</strong>
                <span>{record.source_titles.join("、") || "内容合并"}</span>
              </div>
              <small>
                {new Intl.DateTimeFormat("zh-CN").format(
                  parseApiDate(record.created_at),
                )}
              </small>
            </div>
          )) : <Typography.Text type="secondary">还没有合并记录</Typography.Text>}
        </div>
      </section>

      <section className="settings-section account-section">
        <div>
          <strong>退出当前空间</strong>
          <span>退出后，本机保存的登录令牌会被清除。</span>
        </div>
        <Button onClick={onSignOut}>退出登录</Button>
      </section>
    </div>
  );
}
