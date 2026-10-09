"use client";

import "@ant-design/v5-patch-for-react-19";
import { useEffect } from "react";
import { App, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

import { hydrateAppStore } from "@/stores/app-store";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    hydrateAppStore();
  }, []);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#5f7f69",
          colorInfo: "#6688a8",
          colorSuccess: "#6e9b7d",
          colorWarning: "#d5a45d",
          colorError: "#c87878",
          colorText: "#24312a",
          colorTextSecondary: "#748078",
          colorBgLayout: "#f6f8f6",
          colorBorderSecondary: "#e9eeea",
          borderRadius: 12,
          borderRadiusLG: 20,
          controlHeight: 42,
          fontFamily:
            '"Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
          boxShadowSecondary: "0 16px 50px rgba(44, 66, 52, 0.10)",
        },
        components: {
          Button: {
            primaryShadow: "0 8px 22px rgba(95, 127, 105, 0.22)",
            fontWeight: 600,
          },
          Card: {
            headerBg: "transparent",
          },
          Modal: {
            borderRadiusLG: 24,
          },
          Drawer: {
            colorBgElevated: "#fbfcfb",
          },
          Input: {
            activeShadow: "0 0 0 3px rgba(95, 127, 105, 0.10)",
          },
        },
      }}
    >
      <App>{children}</App>
    </ConfigProvider>
  );
}
