import Playground from '@/components/kics/Playground';

/**
 * K-ICS 现场调试专用干净对话页
 * 访问路径：/lishui/chat
 * 与首页共用同一套对话组件（Playground variant='lishui'），
 * 仅做减法：去掉侧边栏（全局布局跳过）、logo/标题、顶部功能区、底部标语，
 * 保留 Agentic Data Driven Decisions 副标题和常用问题，
 * 完整保留对话窗口能力（输入面板、工具按钮、模型选择、上传、对话渲染等）。
 */
export default function LishuiChatPage() {
  return <Playground variant='lishui' />;
}
