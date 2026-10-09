"use client";

import { useEffect, useState } from "react";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  StarFilled,
} from "@ant-design/icons";
import {
  App,
  Button,
  Checkbox,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Skeleton,
  Tag,
  Typography,
} from "antd";

import { ApiError, templateApi } from "@/services/api";
import type { SummaryTemplate } from "@/types";

export function TemplatesView() {
  const { message } = App.useApp();
  const [items, setItems] = useState<SummaryTemplate[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<SummaryTemplate | null>(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const result = await templateApi.list();
      setItems(result.data);
      setLoaded(true);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "模板加载失败");
    } finally {
      setLoading(false);
    }
  };

  const openEditor = (item?: SummaryTemplate) => {
    setEditing(item || null);
    form.setFieldsValue(
      item || {
        name: "",
        description: "",
        default_style: "medium",
        is_default: false,
        fields: [
          { name: "summary", label: "内容摘要", required: true, max_length: 300 },
          { name: "points", label: "核心知识点", required: true, max_length: 800 },
        ],
      },
    );
    setOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    try {
      const result = editing
        ? await templateApi.update(editing.id, values)
        : await templateApi.create(values);
      setItems((current) => {
        const withoutDefault = result.data.is_default
          ? current.map((item) => ({ ...item, is_default: false }))
          : current;
        return editing
          ? withoutDefault.map((item) =>
              item.id === result.data.id ? result.data : item,
            )
          : [result.data, ...withoutDefault];
      });
      message.success(editing ? "模板已更新" : "模板已保存");
      setOpen(false);
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "保存失败");
      throw error;
    }
  };

  const remove = async (id: string) => {
    try {
      await templateApi.remove(id);
      setItems((current) => current.filter((item) => item.id !== id));
      message.success("模板已删除");
    } catch (error) {
      message.error(error instanceof ApiError ? error.message : "删除失败");
    }
  };

  useEffect(() => {
    if (loaded) return;
    const task = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(task);
    // Only load once when entering this view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  return (
    <div className="templates-view view-enter">
      <div className="templates-heading">
        <div>
          <span className="eyebrow">SHAPE YOUR SUMMARY</span>
          <Typography.Title>总结模板</Typography.Title>
          <Typography.Paragraph>
            定义 AI 每次应该提取哪些字段，以及内容需要多详细。
          </Typography.Paragraph>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor()}>
          新建模板
        </Button>
      </div>

      {loading ? (
        <div className="template-grid">
          {[1, 2, 3].map((value) => <div className="template-card" key={value}><Skeleton active /></div>)}
        </div>
      ) : items.length ? (
        <div className="template-grid">
          {items.map((item) => (
            <article className="template-card" key={item.id}>
              <div className="template-card-top">
                <span className="template-mark">{item.is_default ? <StarFilled /> : "✦"}</span>
                {item.is_default && <Tag bordered={false}>默认</Tag>}
              </div>
              <h3>{item.name}</h3>
              <p>{item.description || "自定义知识整理字段"}</p>
              <div className="template-fields">
                {item.fields.map((field) => <span key={field.name}>{field.label}</span>)}
              </div>
              <div className="template-footer">
                <Tag bordered={false}>
                  {item.default_style === "brief"
                    ? "简明"
                    : item.default_style === "detailed"
                    ? "详细"
                    : "中等"}
                </Tag>
                <span>
                  <Button type="text" icon={<EditOutlined />} onClick={() => openEditor(item)} />
                  <Popconfirm
                    title="删除这个模板？"
                    okText="删除"
                    cancelText="保留"
                    onConfirm={() => remove(item.id)}
                  >
                    <Button type="text" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="content-empty">
          <Empty description="还没有自定义模板">
            <Button type="primary" onClick={() => openEditor()}>创建第一个模板</Button>
          </Empty>
        </div>
      )}

      <Modal
        open={open}
        title={editing ? "编辑总结模板" : "新建总结模板"}
        okText="保存模板"
        cancelText="取消"
        onCancel={() => setOpen(false)}
        onOk={save}
        width={680}
        destroyOnHidden
        forceRender
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <div className="template-form-grid">
            <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
              <Input placeholder="例如：技术学习模板" />
            </Form.Item>
            <Form.Item name="default_style" label="默认详略">
              <Select
                options={[
                  { value: "brief", label: "简明" },
                  { value: "medium", label: "中等" },
                  { value: "detailed", label: "详细" },
                ]}
              />
            </Form.Item>
          </div>
          <Form.Item name="description" label="使用说明">
            <Input.TextArea placeholder="这个模板适合整理什么内容？" />
          </Form.Item>
          <Form.List name="fields">
            {(fields, { add, remove: removeField }) => (
              <div className="field-builder">
                <div className="field-builder-heading">
                  <strong>提取字段</strong>
                  <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => add({ required: true })}>
                    添加字段
                  </Button>
                </div>
                {fields.map((field) => {
                  const { key, ...fieldProps } = field;
                  return (
                  <div className="field-row" key={key}>
                    <Form.Item
                      {...fieldProps}
                      name={[fieldProps.name, "label"]}
                      rules={[{ required: true, message: "填写显示名称" }]}
                    >
                      <Input placeholder="显示名称" />
                    </Form.Item>
                    <Form.Item
                      {...fieldProps}
                      name={[fieldProps.name, "name"]}
                      rules={[
                        { required: true, message: "填写字段名" },
                        { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: "使用英文和下划线" },
                      ]}
                    >
                      <Input placeholder="field_name" />
                    </Form.Item>
                    <Form.Item {...fieldProps} name={[fieldProps.name, "max_length"]}>
                      <InputNumber placeholder="字数" min={20} max={5000} />
                    </Form.Item>
                    <Form.Item {...fieldProps} name={[fieldProps.name, "required"]} valuePropName="checked">
                      <Checkbox>必填</Checkbox>
                    </Form.Item>
                    <Button danger type="text" icon={<DeleteOutlined />} onClick={() => removeField(fieldProps.name)} />
                  </div>
                  );
                })}
              </div>
            )}
          </Form.List>
          <Form.Item name="is_default" valuePropName="checked">
            <Checkbox>设为默认模板</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
