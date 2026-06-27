/** 设置页 — API Key 配置 */

import { useState, useEffect } from 'react'
import { get, put } from '../api/client'

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
        })
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
      setMessage('✅ 配置已保存')
      setConfig({ configured: true, provider, model_display: model || provider })
    } catch (err) {
      setMessage(`❌ 保存失败: ${err instanceof Error ? err.message : '未知错误'}`)
    } finally {
      setSaving(false)
    }
  }

  const PROVIDERS = [
    { id: 'openai', name: 'OpenAI', placeholder: 'sk-...' },
    { id: 'deepseek', name: 'DeepSeek', placeholder: 'sk-...' },
    { id: 'groq', name: 'Groq (免费额度)', placeholder: 'gsk_...' },
    { id: 'custom', name: '自定义端点', placeholder: 'your-api-key' },
  ]

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">API 设置</h1>

      {/* 当前状态 */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6">
        <div className="text-sm text-gray-400">当前使用</div>
        <div className="text-lg font-medium text-gray-200">
          {config?.configured ? config.model_display : 'Gemini 2.0 Flash（免费默认）'}
        </div>
      </div>

      {/* 配置自定义 Key */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-bold mb-4">使用你自己的 API Key</h2>
        <p className="text-sm text-gray-500 mb-6">
          填入你的 API Key 后，ArenaView 将优先使用你配置的模型。Key 仅在服务器端使用，不会泄露。
        </p>

        <div className="space-y-4">
          {/* Provider 选择 */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Provider</label>
            <div className="grid grid-cols-2 gap-2">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setProvider(p.id)}
                  className={`text-left p-3 rounded-lg border text-sm transition-colors ${
                    provider === p.id
                      ? 'border-arena-500 bg-arena-900/20 text-arena-400'
                      : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={PROVIDERS.find((p) => p.id === provider)?.placeholder}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-arena-500"
            />
          </div>

          {/* Model（可选）*/}
          <div>
            <label className="block text-sm text-gray-400 mb-2">模型名称（可选，留空使用默认）</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="如 gpt-4o, deepseek-chat, gemini-2.0-flash"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-arena-500"
            />
          </div>

          {/* 状态信息 */}
          {message && (
            <div
              className={`p-3 rounded-lg text-sm ${
                message.startsWith('✅')
                  ? 'bg-green-900/30 text-green-300'
                  : 'bg-red-900/30 text-red-300'
              }`}
            >
              {message}
            </div>
          )}

          {/* 保存 */}
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full bg-arena-600 hover:bg-arena-500 disabled:bg-gray-700 text-white font-medium py-3 rounded-lg transition-colors"
          >
            {saving ? '保存中...' : '保存配置'}
          </button>
        </div>
      </div>

      {/* 说明 */}
      <div className="mt-8 text-sm text-gray-600 space-y-2">
        <p>💡 如何获取免费 API Key：</p>
        <p>· <strong>Groq</strong>: <a href="https://console.groq.com" className="text-arena-500 hover:underline" target="_blank">console.groq.com</a> — 注册即送免费额度，支持 Llama 等开源模型</p>
        <p>· <strong>Gemini</strong>: <a href="https://aistudio.google.com/apikey" className="text-arena-500 hover:underline" target="_blank">aistudio.google.com</a> — 免费额度，每天 1500 次</p>
        <p>· <strong>DeepSeek</strong>: <a href="https://platform.deepseek.com" className="text-arena-500 hover:underline" target="_blank">platform.deepseek.com</a> — 注册送 500 万 token</p>
      </div>
    </div>
  )
}
