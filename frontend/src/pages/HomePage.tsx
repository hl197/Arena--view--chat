import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { post } from '../api/client'
import { useDebateStore } from '../store/debateStore'
import HandDrawnButton from '../components/ui/HandDrawnButton'
import { HandDrawnTextarea, HandDrawnInput } from '../components/ui/HandDrawnInput'
import HandDrawnCard from '../components/ui/HandDrawnCard'

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
    <div className="min-h-screen paper-bg">
      {/* Hero */}
      <div className="max-w-3xl mx-auto pt-16 pb-12 px-4">
        <div className="text-center mb-10">
          <div className="inline-block mb-4">
            <span className="text-5xl">📓</span>
          </div>
          <h1 className="text-4xl font-bold mb-4 text-ink-300 font-hand">
            多视角<span className="text-marker-purple">决策</span>分析
          </h1>
          <p className="text-ink-100 text-lg">
            不是给你一个答案，而是让一群 AI 从不同立场辩论，
            <br />
            帮你理解决策的全貌。
          </p>
          <div className="mt-5">
            <button
              onClick={() => navigate('/debate')}
              className="text-sm text-ink-50 hover:text-marker-blue transition-colors underline-hd border-b border-dashed border-divider pb-0.5"
            >
              📋 查看历史讨论
            </button>
          </div>
        </div>

        {/* 输入卡片 */}
        <HandDrawnCard variant="white" className="p-6 mb-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <HandDrawnTextarea
              label="描述你的决策困境"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="例如：我在北京工作3年，目前租房月租6000，手头有80万存款。父母催买房，但我担心房价继续跌。该不该现在买？"
              rows={4}
              variant="filled"
            />

            <HandDrawnInput
              label="你正在考虑的选项（可选，逗号分隔）"
              value={options}
              onChange={(e) => setOptions(e.target.value)}
              placeholder="买房, 继续租房, 搬到郊区买"
              variant="filled"
            />

            {error && (
              <div className="bg-marker-red/10 border-2 border-marker-red/40 rounded-hd-md p-3 text-marker-red text-sm hd-filter">
                ⚠️ {error}
              </div>
            )}

            <HandDrawnButton
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              tilt="right"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">✏️</span>
                  正在组建专家团...
                </span>
              ) : (
                <>开始分析 →</>
              )}
            </HandDrawnButton>
          </form>
        </HandDrawnCard>

        {/* 示例问题 */}
        <div>
          <p className="text-sm text-ink-50 mb-4 font-medium">
            ✏️ 试试这些问题：
          </p>
          <div className="grid gap-3">
            {EXAMPLE_QUESTIONS.map((eq, i) => (
              <button
                key={i}
                onClick={() => setQuestion(eq.text)}
                className="text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sticky-hover"
              >
                <HandDrawnCard variant="white" className="p-4">
                  <span className="mr-2 text-lg">{eq.icon}</span>
                  <span className="text-ink-200 text-sm">{eq.text}</span>
                </HandDrawnCard>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 底部装饰 */}
      <div className="text-center pb-8 text-ink-50 text-xs opacity-60">
        ✨ 你的每一个决策，都值得被认真对待
      </div>
    </div>
  )
}
