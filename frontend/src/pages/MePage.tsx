import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import HandDrawnCard from '../components/ui/HandDrawnCard'
import HandDrawnAvatar from '../components/ui/HandDrawnAvatar'
import HandDrawnButton from '../components/ui/HandDrawnButton'
import HandDrawnDivider from '../components/ui/HandDrawnDivider'
import { useUserStore, getUserAvatar, type UserGender } from '../store/userStore'
import { useAuthStore } from '../store/authStore'
import { get } from '../api/client'

interface QuotaInfo {
  tier: string
  daily_debates_used: number
  daily_debates_limit: number
  total_tokens_used: number
  total_tokens_limit: number
  api_key_configured: boolean
}

/** 各套餐配置（与后端 config.py / init_quota 保持一致） */
const TIER_CONFIG: Record<string, { label: string; color: string; perspectives: number; rounds: number }> = {
  guest:      { label: '游客',   color: '#9ca3af', perspectives: 4, rounds: 1 },
  registered: { label: '已注册', color: '#3b82f6', perspectives: 5, rounds: 2 },
  pro:        { label: '专业版', color: '#f59e0b', perspectives: 6, rounds: 3 },
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

/** 进度条：已用量 / 限额，无限额时显示 "无上限" */
function QuotaBar({ used, limit, label, suffix, unlimited }: { used: number; limit: number; label: string; suffix?: string; unlimited?: boolean }) {
  if (unlimited) {
    return (
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-ink-50">{label}</span>
          <span className="text-marker-gold font-medium">∞ 无上限</span>
        </div>
        <div className="h-2 bg-paper-200 rounded-full overflow-hidden border border-divider/50">
          <div className="h-full rounded-full bg-marker-gold/30" style={{ width: '100%' }} />
        </div>
      </div>
    )
  }
  const pct = Math.min((used / limit) * 100, 100)
  const warn = pct > 80
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-ink-50">{label}</span>
        <span className={warn ? 'text-marker-red font-medium' : 'text-ink-100'}>
          {suffix ? `${used}${suffix} / ${limit}${suffix}` : `${used} / ${limit}`}
        </span>
      </div>
      <div className="h-2 bg-paper-200 rounded-full overflow-hidden border border-divider/50">
        <div
          className={`h-full rounded-full transition-all duration-500 ${warn ? 'bg-marker-red/70' : 'bg-marker-blue/60'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function MePage() {
  const navigate = useNavigate()
  const { gender, nickname, setGender, setNickname } = useUserStore()
  const { isLoggedIn, user, logout } = useAuthStore()
  const [quota, setQuota] = useState<QuotaInfo | null>(null)

  // 登录后拉取额度
  useEffect(() => {
    if (!isLoggedIn) return
    get<QuotaInfo>('/user/quota').then(setQuota).catch(() => {})
  }, [isLoggedIn])

  const tier = quota?.tier || user?.tier || 'guest'
  const tierCfg = TIER_CONFIG[tier] || TIER_CONFIG.guest

  return (
    <div className="min-h-screen paper-bg">
      <div className="max-w-2xl mx-auto pt-16 pb-12 px-4">
        {/* 返回 */}
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-ink-50 hover:text-ink-200 transition-colors mb-8 flex items-center gap-1"
        >
          ← 返回
        </button>

        {/* 头像区域 */}
        <div className="flex flex-col items-center mb-10">
          <HandDrawnAvatar
            src={getUserAvatar(gender)}
            content="😊"
            color={gender === 'male' ? 'blue' : 'pink'}
            size="xl"
          />
          <h2 className="text-xl font-bold text-ink-300 mt-4 font-hand">{nickname}</h2>
          <p className="text-ink-50 text-sm mt-1">你的头像和偏好</p>
        </div>

        {/* 头像选择 */}
        <HandDrawnCard variant="white" className="p-6 mb-6">
          <h3 className="text-sm font-bold text-ink-200 mb-4 flex items-center gap-2">
            <span>👤</span> 选择头像
          </h3>
          <div className="flex gap-6 justify-center">
            {/* 男性 */}
            <button
              onClick={() => setGender('male')}
              className={`flex flex-col items-center gap-2 p-4 rounded-hd-md border-2 transition-all ${
                gender === 'male'
                  ? 'border-marker-blue bg-marker-blue/10 scale-105'
                  : 'border-divider hover:border-marker-blue/40'
              }`}
            >
              <HandDrawnAvatar
                src="/avatars/user-male.svg"
                content="👦"
                color="blue"
                size="lg"
              />
              <span className={`text-xs font-medium ${gender === 'male' ? 'text-marker-blue' : 'text-ink-100'}`}>
                男生
              </span>
              {gender === 'male' && (
                <span className="text-marker-blue text-[10px] bg-marker-blue/15 px-2 py-0.5 rounded-full">
                  当前
                </span>
              )}
            </button>

            {/* 女性 */}
            <button
              onClick={() => setGender('female')}
              className={`flex flex-col items-center gap-2 p-4 rounded-hd-md border-2 transition-all ${
                gender === 'female'
                  ? 'border-marker-pink bg-marker-pink/10 scale-105'
                  : 'border-divider hover:border-marker-pink/40'
              }`}
            >
              <HandDrawnAvatar
                src="/avatars/user-female.svg"
                content="👧"
                color="pink"
                size="lg"
              />
              <span className={`text-xs font-medium ${gender === 'female' ? 'text-marker-pink' : 'text-ink-100'}`}>
                女生
              </span>
              {gender === 'female' && (
                <span className="text-marker-pink text-[10px] bg-marker-pink/15 px-2 py-0.5 rounded-full">
                  当前
                </span>
              )}
            </button>
          </div>
        </HandDrawnCard>

        {/* 昵称 */}
        <HandDrawnCard variant="white" className="p-6 mb-6">
          <h3 className="text-sm font-bold text-ink-200 mb-4 flex items-center gap-2">
            <span>✏️</span> 昵称
          </h3>
          <div className="flex gap-3">
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="你的昵称"
              maxLength={12}
              className="flex-1 px-4 py-2.5 bg-paper-100 border-2 border-divider rounded-hd-md text-sm text-ink-300 focus:outline-none focus:border-marker-blue transition-colors"
            />
            <span className="text-xs text-ink-50 self-center">{nickname.length}/12</span>
          </div>
        </HandDrawnCard>

        {/* 账号 & 额度 */}
        <HandDrawnCard variant="white" className="p-6 mb-6">
          <h3 className="text-sm font-bold text-ink-200 mb-4 flex items-center gap-2">
            <span>🔐</span> 账号 & 额度
          </h3>
          {isLoggedIn ? (
            <div className="space-y-4">
              {/* 基本信息 */}
              <div className="space-y-2 text-sm text-ink-200">
                <div className="flex justify-between">
                  <span className="text-ink-50">邮箱</span>
                  <span>{user?.email}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-ink-50">套餐</span>
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-medium"
                    style={{ backgroundColor: `${tierCfg.color}18`, color: tierCfg.color }}
                  >
                    {tierCfg.label}
                  </span>
                </div>
              </div>

              {/* 额度详情 */}
              {quota && (
                <>
                  <HandDrawnDivider variant="dashed" />
                  {/* 用自己的 Key → 无上限提示 */}
                  {quota.api_key_configured && (
                    <div className="bg-marker-gold/8 border border-marker-gold/30 rounded-hd-sm p-3 text-xs text-ink-100 flex items-center gap-2">
                      <span>🔑</span>
                      <span>你正在使用自己的 API Key，不受平台额度限制</span>
                    </div>
                  )}
                  <div className="space-y-3">
                    <QuotaBar
                      used={quota.daily_debates_used}
                      limit={quota.daily_debates_limit}
                      label="今日辩论次数"
                      unlimited={quota.api_key_configured}
                    />
                    <QuotaBar
                      used={quota.total_tokens_used}
                      limit={quota.total_tokens_limit}
                      label="Token 用量"
                      unlimited={quota.api_key_configured}
                    />
                  </div>
                  <HandDrawnDivider variant="dashed" />
                  <div className="flex gap-3 text-xs text-ink-100">
                    <div className="flex-1 bg-paper-100 rounded-hd-sm p-2.5 text-center border border-divider/50">
                      <div className="text-ink-50 mb-0.5">最大视角</div>
                      <div className="font-bold text-ink-300">{quota.api_key_configured ? '∞' : `${tierCfg.perspectives} 个`}</div>
                    </div>
                    <div className="flex-1 bg-paper-100 rounded-hd-sm p-2.5 text-center border border-divider/50">
                      <div className="text-ink-50 mb-0.5">辩论轮次</div>
                      <div className="font-bold text-ink-300">{quota.api_key_configured ? '∞' : `${tierCfg.rounds} 轮`}</div>
                    </div>
                    <div className="flex-1 bg-paper-100 rounded-hd-sm p-2.5 text-center border border-divider/50">
                      <div className="text-ink-50 mb-0.5">Token 上限</div>
                      <div className="font-bold text-ink-300">{quota.api_key_configured ? '∞' : fmtTokens(quota.total_tokens_limit)}</div>
                    </div>
                  </div>
                </>
              )}

              <HandDrawnDivider variant="dashed" />
              <button
                onClick={logout}
                className="text-marker-red text-xs hover:underline"
              >
                退出登录
              </button>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-sm text-ink-50 mb-3">登录后查看账号信息与额度</p>
              <Link
                to="/auth"
                className="inline-block px-4 py-2 rounded-hd-md border-2 border-marker-blue/30 text-marker-blue text-sm hover:bg-marker-blue/5 transition-all hd-filter"
              >
                去登录
              </Link>
            </div>
          )}
        </HandDrawnCard>

        {/* 关于 */}
        <HandDrawnCard variant="white" className="p-6">
          <h3 className="text-sm font-bold text-ink-200 mb-4 flex items-center gap-2">
            <span>📓</span> 关于 ArenaView
          </h3>
          <p className="text-sm text-ink-100 leading-relaxed">
            AI 不做你的决策，AI 帮你理解决策的全貌，你自己选。
          </p>
          <HandDrawnDivider variant="dashed" className="my-4" />
          <div className="text-xs text-ink-50 space-y-1">
            <p>版本 v0.2.0</p>
            <p>手绘手账风 · 多智能体群聊决策分析</p>
          </div>
        </HandDrawnCard>
      </div>
    </div>
  )
}
