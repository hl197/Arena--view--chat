/** 微信风格时间戳——居中显示 */
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
    <div className="flex justify-center my-3">
      <span className="text-[10px] text-gray-400 bg-gray-200/70 rounded px-2 py-[2px]">
        {label}
      </span>
    </div>
  )
}
