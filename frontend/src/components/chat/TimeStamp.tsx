/** 手绘风格时间戳——居中显示 */
interface TimeStampProps {
  time: number  // unix ms
}

export default function TimeStamp({ time }: TimeStampProps) {
  const d = new Date(time)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()

  const timeStr = d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  const label = isToday ? timeStr : `${d.getMonth() + 1}月${d.getDate()}日 ${timeStr}`

  return (
    <div className="flex justify-center my-4">
      <span className="text-[11px] text-ink-50 bg-paper-200/70 border border-dashed border-divider rounded-full px-3 py-1 hd-filter">
        {label}
      </span>
    </div>
  )
}
