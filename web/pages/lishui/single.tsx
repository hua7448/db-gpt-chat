import { useEffect, useRef, useState } from 'react';

import Playground from '@/components/kics/Playground';

/**
 * 设计基准宽度。宿主容器窄于它时整体等比缩小，避免内容横向被裁。
 * 想调"多大开始缩"，改这个值即可。
 */
const DESIGN_WIDTH = 1280;

/**
 * K-ICS 单栏对话页
 * 访问路径：/lishui/single
 *
 * 与 /lishui/chat 共用同一套对话组件（Playground variant='single'）。区别是布局：
 * 不渲染右侧结果面板，每一轮的产物（报告、图表、图片）直接展开在该轮回答下方，
 * 代码与附件折叠。
 *
 * 自适应：外层按宿主容器宽度做等比缩放（transform: scale）。因为全站布局是
 * `w-screen h-screen overflow-hidden` 且没有响应式断点，直接嵌进窄容器（iframe /
 * 门户右侧栏）时右侧会被裁掉；这里按 DESIGN_WIDTH 等比缩到容器宽度，保证完整可见。
 */
export default function LishuiSinglePage() {
  const hostRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const fit = () => {
      const w = host.clientWidth || window.innerWidth;
      setScale(w > 0 && w < DESIGN_WIDTH ? w / DESIGN_WIDTH : 1);
    };

    fit();
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(fit) : null;
    observer?.observe(host);
    window.addEventListener('resize', fit);

    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', fit);
    };
  }, []);

  return (
    <div ref={hostRef} className='h-full w-full overflow-hidden'>
      <div
        className='h-full w-full'
        style={
          scale < 1
            ? {
                transform: `scale(${scale})`,
                transformOrigin: 'top left',
                // 宽度/高度反向补偿，缩放后仍铺满宿主容器
                width: `${100 / scale}%`,
                height: `${100 / scale}%`,
              }
            : undefined
        }
      >
        <Playground variant='single' />
      </div>
    </div>
  );
}
