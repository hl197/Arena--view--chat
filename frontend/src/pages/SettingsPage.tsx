/** 设置页 — API Key 配置 · 手绘风格 */

import { useState, useEffect } from 'react'
import { get, put } from '../api/client'
import HandDrawnButton from '../components/ui/HandDrawnButton'
import { HandDrawnInput } from '../components/ui/HandDrawnInput'
import HandDrawnCard from '../components/ui/HandDrawnCard'
import HandDrawnBadge from '../components/ui/HandDrawnBadge'
import HandDrawnDivider from '../components/ui/HandDrawnDivider'

export default function SettingsPage() {
  const [config, setConfig] = useState<{
    configured: boolean
    provider: string
    model_display: string
  } | null>(null)
  const [provider, setProvider] = useState('openai')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    get<Record<string, unknown>>('/user/llm-config')
      .then((res) =>
        setConfig({
          configured: res.configured as boolean,
          provider: res.provider as string,
          model_display: res.model_display as string,
        }),
      )
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setMessage('请输入 API Key')
      return
    }
    setSaving(true)
    setMessage('')
    try {
      await put('/user/llm-config', {
        provider,
        api_key: apiKey,
        model: model || '',
        base_url: provider === 'custom' ? 'https://your-endpoint.com/v1' : '',
      })
      setMessage('success')
      setConfig({ configured: true, provider, model_display: model || provider })
    } catch (err) {
      setMessage(`❌ 保存失败: ${err instanceof Error ? err.message : '未知错误'}`)
    } finally {
      setSaving(false)
    }
  }

  const PROVIDERS = [
    { id: 'openai', name: 'OpenAI', placeholder: 'sk-...', color: 'green' as const },
    { id: 'deepseek', name: 'DeepSeek', placeholder: 'sk-...', color: 'blue' as const },
    { id: 'groq', name: 'Groq (免费额度)', placeholder: 'gsk_...', color: 'warning' as const },
    { id: 'custom', name: '自定义端点', placeholder: 'your-api-key', color: 'purple' as const },
  ]

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-2 text-ink-300 font-hand">⚙️ API 设置</h1>
      <p className="text-ink-50 mb-8 text-sm">配置你的 API Key，让 AI 帮你做决策分析</p>

      {/* 当前状态卡片 */}
      <HandDrawnCard variant="white" className="p-5 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-ink-50 mb-1">当前使用</div>
            <div className="text-lg font-semibold text-ink-300">
              {config?.configured ? config.model_display : 'DeepSeek（免费默认）'}
            </div>
          </div>
          <HandDrawnBadge variant={config?.configured ? 'success' : 'info'} dot size="md">
            {config?.configured ? '已配置' : '默认模型'}
          </HandDrawnBadge>
        </div>
      </HandDrawnCard>

      {/* 配置自定义 Key */}
      <HandDrawnCard variant="white" className="p-6">
        <h2 className="text-lg font-bold mb-2 text-ink-300">🔑 使用你自己的 API Key</h2>
        <p className="text-sm text-ink-50 mb-6">
          填入你的 API Key 后，ArenaView 将优先使用你配置的模型。
          Key 仅在服务器端使用，不会泄露。
        </p>

        <div className="space-y-5">
          {/* Provider 选择 */}
          <div>
            <label className="block text-sm text-ink-100 mb-3 font-medium">选择 Provider</label>
            <div className="grid grid-cols-2 gap-3">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setProvider(p.id)}
                  className={`
                    text-left p-3 rounded-hd-md border-2 hd-filter text-sm transition-all
                    ${provider === p.id
                      ? 'border-marker-blue bg-marker-blue/10 text-ink-300 shadow-hd-sm'
                      : 'border-divider bg-paper-50 text-ink-100 hover:border-marker-blue/50 hover:bg-paper-100'
                    }
                  `}
                >
                  <span className="font-medium">{p.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* API Key */}
          <HandDrawnInput
            label="API Key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={PROVIDERS.find((p) => p.id === provider)?.placeholder}
            variant="filled"
          />

          {/* Model（可选） */}
          <HandDrawnInput
            label="模型名称（可选，留空使用默认）"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="如 gpt-4o, deepseek-chat, gemini-2.0-flash"
            variant="filled"
          />

          {/* 状态信息 */}
          {message === 'success' && (
            <div className="bg-marker-green/15 border-2 border-marker-green/40 rounded-hd-md p-3 text-marker-green text-sm hd-filter">
              ✅ 配置已保存！
            </div>
          )}
          {message && message !== 'success' && (
            <div className="bg-marker-red/10 border-2 border-marker-red/40 rounded-hd-md p-3 text-marker-red text-sm hd-filter">
              {message}
            </div>
          )}

          {/* 保存按钮 */}
          <HandDrawnButton
            onClick={handleSave}
            variant="primary"
            size="lg"
            fullWidth
            tilt="right"
            disabled={saving}
          >
            {saving ? '保存中...' : '💾 保存配置'}
          </HandDrawnButton>
        </div>
      </HandDrawnCard>

      <HandDrawnDivider variant="doodle" className="my-8" />

      {/* 获取 Key 说明 */}
      <div className="text-sm text-ink-50 space-y-2 px-2">
        <p className="font-medium text-ink-200 mb-3">💡 如何获取免费 API Key：</p>
        <p className="flex items-start gap-2">
          <span className="text-marker-blue">•</span>
          <span>
            <strong className="text-ink-200">Groq</strong>:{' '}
            <a
              href="https://console.groq.com"
              className="text-marker-blue hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              console.groq.com
            </a>{' '}
            — 注册即送免费额度，支持 Llama 等开源模型
          </span>
        </p>
        <p className="flex items-start gap-2">
          <span className="text-marker-blue">•</span>
          <span>
            <strong className="text-ink-200">Gemini</strong>:{' '}
            <a
              href="https://aistudio.google.com/apikey"
              className="text-marker-blue hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              aistudio.google.com
            </a>{' '}
            — 免费额度，每天 1500 次
          </span>
        </p>
        <p className="flex items-start gap-2">
          <span className="text-marker-blue">•</span>
          <span>
            <strong className="text-ink-200">DeepSeek</strong>:{' '}
            <a
              href="https://platform.deepseek.com"
              className="text-marker-blue hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              platform.deepseek.com
            </a>{' '}
            — 注册送 500 万 token
          </span>
        </p>
      </div>
    </div>
  )
}
