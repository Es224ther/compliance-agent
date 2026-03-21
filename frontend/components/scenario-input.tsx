"use client";

const PLACEHOLDER = `请描述你的 AI 功能场景，例如：

• 涉及哪些用户数据（姓名、人脸、行为数据等）
• 数据在哪些地区流转（国内、欧洲、全球）
• 是否使用第三方模型（GPT-4、Claude 等）
• AI 生成内容是否直接面向终端用户`;

const PRESETS = [
  {
    label: "跨境数据训练",
    text: "我们计划把欧洲用户上传的短视频素材传回国内服务器，用于训练一个 AI 视频剪辑模型。训练完成后模型部署在国内，服务全球用户，视频中包含用户的人脸画面。",
  },
  {
    label: "第三方 API 调用",
    text: "我们的产品打算接入 GPT-4o 的 API 来处理欧洲用户提交的文本和图片，主要是做内容摘要和智能标签。用户数据会直接发送到 OpenAI 的服务器进行处理，处理完的结果返回给我们的应用展示给用户。",
  },
  {
    label: "AIGC 内容标识",
    text: "我们正在开发一个面向欧洲 B 端客户的 API 服务，客户可以通过这个 API 自动生成广告短视频。生成的视频会直接由客户投放到 Instagram、TikTok 等社交平台上。",
  },
] as const;

interface ScenarioInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
}

export default function ScenarioInput({
  value,
  onChange,
  onSubmit,
  isLoading,
}: ScenarioInputProps) {
  const isReady = !isLoading;

  return (
    <div className="flex flex-col gap-3">
      <textarea
        className="glass-input p-4 min-h-[180px]"
        style={{ fontSize: "14px", lineHeight: "1.75" }}
        placeholder={PLACEHOLDER}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading}
        aria-label="AI 场景描述"
      />

      {/* Preset scenarios */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs shrink-0" style={{ color: "#71717a" }}>
          或试试预设场景：
        </span>
        {PRESETS.map((p, i) => (
          <button
            key={p.label}
            type="button"
            className="text-xs px-2.5 py-1 rounded-md transition-colors duration-150"
            style={{
              background: "transparent",
              color: "#a1a1aa",
              border: "1px solid rgba(255,255,255,0.08)",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = "#fafafa";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.2)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = "#a1a1aa";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.08)";
            }}
            onClick={() => onChange(p.text)}
            aria-label={`填充预设场景：${p.label}`}
          >
            {p.label}
            {i < PRESETS.length - 1 && (
              <span className="ml-1.5" style={{ color: "#3f3f46" }}>·</span>
            )}
          </button>
        ))}
      </div>

      <button
        className="btn-accent w-full py-3"
        onClick={onSubmit}
        disabled={!isReady}
        aria-label="开始合规评估"
      >
        {isLoading ? (
          <>
            <svg className="spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M21 12a9 9 0 11-6.219-8.56" strokeLinecap="round" />
            </svg>
            评估中…
          </>
        ) : (
          <>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
            开始评估
          </>
        )}
      </button>
    </div>
  );
}
