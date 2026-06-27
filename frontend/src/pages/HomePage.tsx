import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { post } from '../api/client'
import { useDebateStore } from '../store/debateStore'

const EXAMPLE_QUESTIONS = [
  { icon: '🏠', text: '在上海工作5年存款50万，该买房还是继续租房？' },
  { icon: '💼', text: '收到创业公司offer降薪30%但给期权，该不该去？' },
  { icon: '📚', text: '孩子教育该走应试路线还是国际路线？' },
  { icon: '💰', text: '现在该投资黄金、股票还是持有现金？' },
]

export default function HomePage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [options, setOptions] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { setSessionId, setQuestion: storeQuestion, setPhase } = useDebateStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (question.trim().length < 10) {
      setError('请详细描述你的决策困境（至少10个字）')
      return
    }

    setLoading(true)
    setError('')

    try {
      const res = await post<{ session_id: string; stream_url: string }>('/debate/start', {
        question: question.trim(),
        options: options
          .split(',')
          .map((o) => o.trim())
          .filter(Boolean),
        num_perspectives: 5,
        debate_rounds: 2,
      })

      setSessionId(res.session_id)
      storeQuestion(question.trim())
      setPhase('generating')
      navigate(`/debate/${res.session_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动失败，请稍后重试')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto mt-16">
      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4">
          <span className="text-arena-500">多视角</span> 决策分析
        </h1>
        <p className="text-gray-400 text-lg">
          不是给你一个答案，而是让一群 AI 从不同立场辩论，帮你理解决策的全貌。
        </p>
      </div>

      {/* 输入区域 */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">
            描述你的决策困境
          </label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="例如：我在北京工作3年，目前租房月租6000，手头有80万存款。父母催买房，但我担心房价继续跌。该不该现在买？"
            rows={4}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg p-4 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-arena-500 transition-colors resize-none"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">
            你正在考虑的选项（可选，逗号分隔）
          </label>
          <input
            type="text"
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            placeholder="买房, 继续租房, 搬到郊区买"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-arena-500 transition-colors"
          />
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-arena-600 hover:bg-arena-500 disabled:bg-gray-700 text-white font-medium py-4 rounded-lg transition-colors text-lg"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin">⚔️</span>
              正在生成视角...
            </span>
          ) : (
            '开始分析'
          )}
        </button>
      </form>

      {/* 示例问题 */}
      <div className="mt-12">
        <p className="text-sm text-gray-500 mb-4">试试这些问题：</p>
        <div className="grid gap-3">
          {EXAMPLE_QUESTIONS.map((eq, i) => (
            <button
              key={i}
              onClick={() => setQuestion(eq.text)}
              className="text-left bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-lg p-4 transition-colors"
            >
              <span className="mr-2">{eq.icon}</span>
              <span className="text-gray-300">{eq.text}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 工作原理 */}
      <div className="mt-16 border-t border-gray-800 pt-12">
        <h2 className="text-xl font-bold mb-6 text-center">工作原理</h2>
        <div className="grid grid-cols-4 gap-4">
          {[
            { step: '1', icon: '🎯', title: '视角生成', desc: '拆解为4-6个不同立场' },
            { step: '2', icon: '🔍', title: '独立研究', desc: '每个视角搜索论证' },
            { step: '3', icon: '⚔️', title: '交叉辩论', desc: '视角之间互相质疑' },
            { step: '4', icon: '🗺️', title: '决策地图', desc: '帮你理解决策全貌' },
          ].map((item) => (
            <div key={item.step} className="text-center">
              <div className="text-2xl mb-2">{item.icon}</div>
              <div className="text-sm font-medium text-gray-200">{item.title}</div>
              <div className="text-xs text-gray-500 mt-1">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
