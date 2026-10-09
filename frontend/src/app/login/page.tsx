"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRightOutlined,
  BulbOutlined,
  CheckCircleFilled,
  LockOutlined,
  MailOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { App, Button, Form, Input, Segmented, Typography } from "antd";

import { ApiError, authApi } from "@/services/api";
import { useAppStore } from "@/stores/app-store";

type LoginValues = {
  username?: string;
  email: string;
  password: string;
};

export default function LoginPage() {
  const router = useRouter();
  const { message } = App.useApp();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const hydrated = useAppStore((state) => state.hydrated);
  const token = useAppStore((state) => state.token);
  const signIn = useAppStore((state) => state.signIn);

  useEffect(() => {
    if (hydrated && token) router.replace("/");
  }, [hydrated, router, token]);

  const submit = async (values: LoginValues) => {
    setLoading(true);
    try {
      if (mode === "register") {
        await authApi.register({
          username: values.username!.trim(),
          email: values.email.trim(),
          password: values.password,
        });
      }
      const result = await authApi.login({
        email: values.email.trim(),
        password: values.password,
      });
      signIn(result.data.access_token);
      message.success(mode === "register" ? "空间创建好了，开始生长吧" : "欢迎回来");
      router.replace("/");
    } catch (error) {
      message.error(
        error instanceof ApiError ? error.message : "操作没有成功，请稍后再试",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="auth-brand">
          <span className="brand-mark">
            <BulbOutlined />
          </span>
          <span>KnowFlow</span>
        </div>
        <div className="story-copy">
          <span className="eyebrow">A SPACE FOR GROWING IDEAS</span>
          <Typography.Title>让零散的灵感，长成自己的知识体系。</Typography.Title>
          <Typography.Paragraph>
            收藏不再是终点。KnowFlow 会帮你提炼、连接和回看，让每一次记录都成为下一次思考的起点。
          </Typography.Paragraph>
          <div className="story-points">
            <span><CheckCircleFilled /> 多种内容，随手收进来</span>
            <span><CheckCircleFilled /> AI 自动提炼成知识点</span>
            <span><CheckCircleFilled /> 越用越懂你的知识空间</span>
          </div>
        </div>
        <div className="auth-orbit auth-orbit-one" />
        <div className="auth-orbit auth-orbit-two" />
        <div className="floating-note floating-note-one">
          <span className="floating-dot mint" />
          <div><strong>设计灵感</strong><small>刚刚长出 3 个知识点</small></div>
        </div>
        <div className="floating-note floating-note-two">
          <span className="floating-dot butter" />
          <div><strong>本周回顾</strong><small>12 条新连接</small></div>
        </div>
      </section>

      <section className="auth-form-wrap">
        <div className="auth-form-card">
          <div className="mobile-brand">
            <span className="brand-mark"><BulbOutlined /></span>
            <span>KnowFlow</span>
          </div>
          <Segmented
            block
            value={mode}
            onChange={(value) => setMode(value as "login" | "register")}
            options={[
              { label: "登录", value: "login" },
              { label: "创建账号", value: "register" },
            ]}
          />
          <div className="auth-form-heading">
            <Typography.Title level={2}>
              {mode === "login" ? "继续你的知识旅程" : "创建你的知识空间"}
            </Typography.Title>
            <Typography.Text type="secondary">
              {mode === "login"
                ? "灵感和知识都在原地等你。"
                : "从第一条笔记开始，让知识自然生长。"}
            </Typography.Text>
          </div>
          <Form<LoginValues>
            layout="vertical"
            requiredMark={false}
            onFinish={submit}
          >
            {mode === "register" && (
              <Form.Item
                name="username"
                label="怎么称呼你"
                rules={[
                  { required: true, message: "请输入你的名字" },
                  { min: 2, message: "至少输入 2 个字符" },
                ]}
              >
                <Input prefix={<UserOutlined />} placeholder="你的昵称" />
              </Form.Item>
            )}
            <Form.Item
              name="email"
              label="邮箱"
              rules={[
                { required: true, message: "请输入邮箱" },
                { type: "email", message: "请输入有效的邮箱地址" },
              ]}
            >
              <Input prefix={<MailOutlined />} placeholder="you@example.com" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: "请输入密码" },
                { min: 6, message: "密码至少需要 6 位" },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="至少 6 位"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              iconPosition="end"
              icon={<ArrowRightOutlined />}
              className="auth-submit"
            >
              {mode === "login" ? "进入 KnowFlow" : "开始使用"}
            </Button>
          </Form>
          <Typography.Text className="auth-footnote" type="secondary">
            你的知识数据由自己的服务保存，适合本地或私有化部署。
          </Typography.Text>
        </div>
      </section>
    </main>
  );
}
