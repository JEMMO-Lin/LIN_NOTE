import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "KnowFlow · 让知识自然生长",
  description: "自动整理、连接并生长的个人知识空间",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AntdRegistry>
          <Providers>{children}</Providers>
        </AntdRegistry>
      </body>
    </html>
  );
}
