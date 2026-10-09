"use client";

import { useEffect } from "react";
import { App, Form, Input, Modal, Select } from "antd";

import { ApiError, knowledgeBaseApi } from "@/services/api";
import type { KnowledgeBase, KnowledgeBaseInput } from "@/types";

type Props = {
  open: boolean;
  editing?: KnowledgeBase | null;
  onClose: () => void;
  onSaved: (item: KnowledgeBase) => void;
};

const categoryOptions = [
  "学习成长",
  "工作项目",
  "设计灵感",
  "生活记录",
  "兴趣探索",
  "其他",
].map((value) => ({ value, label: value }));

export function KnowledgeBaseModal({
  open,
  editing,
  onClose,
  onSaved,
}: Props) {
  const [form] = Form.useForm<KnowledgeBaseInput>();
  const { message } = App.useApp();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue({
      name: editing?.name || "",
      description: editing?.description || "",
      category: editing?.category || undefined,
      tags: editing?.tags || [],
    });
  }, [editing, form, open]);

  const submit = async () => {
    const values = await form.validateFields();
    try {
      const result = editing
        ? await knowledgeBaseApi.update(editing.id, values)
        : await knowledgeBaseApi.create(values);
      message.success(editing ? "知识库已更新" : "新的知识库已种下");
      onSaved(result.data);
      onClose();
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "保存失败");
      throw error;
    }
  };

  return (
    <Modal
      open={open}
      title={editing ? "编辑知识库" : "新建知识库"}
      okText={editing ? "保存修改" : "创建知识库"}
      cancelText="取消"
      onCancel={onClose}
      onOk={submit}
      destroyOnHidden
      forceRender
      centered
      className="soft-modal"
    >
      <p className="modal-intro">
        给一类持续关注的主题留出独立空间，之后收进来的内容会在这里慢慢长成体系。
      </p>
      <Form form={form} layout="vertical" requiredMark={false}>
        <Form.Item
          name="name"
          label="知识库名称"
          rules={[
            { required: true, message: "请输入知识库名称" },
            { max: 100, message: "名称不能超过 100 个字符" },
          ]}
        >
          <Input placeholder="例如：产品设计灵感" autoFocus />
        </Form.Item>
        <Form.Item name="description" label="一句话描述">
          <Input.TextArea
            placeholder="这个空间准备收集什么？"
            autoSize={{ minRows: 3, maxRows: 5 }}
          />
        </Form.Item>
        <Form.Item name="category" label="分类">
          <Select
            allowClear
            showSearch
            placeholder="选择或输入分类"
            options={categoryOptions}
          />
        </Form.Item>
        <Form.Item name="tags" label="标签">
          <Select
            mode="tags"
            tokenSeparators={[",", "，"]}
            placeholder="输入后回车，可添加多个"
            maxCount={6}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
