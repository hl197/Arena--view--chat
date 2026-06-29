import { Link } from 'react-router-dom'

export default function Header() {
  return (
    <header className="border-b-2 border-divider bg-paper-100/80 backdrop-blur hd-filter">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-ink-300">
          <span className="text-marker-purple">📓</span>
          <span className="font-hand tracking-wider">ArenaView</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm text-ink-100">
          <Link
            to="/settings"
            className="px-3 py-1.5 rounded-hd-md border-2 border-transparent hover:border-divider hover:bg-paper-200 transition-all hd-filter"
          >
            <span className="mr-1.5">⚙️</span>
            API 设置
          </Link>
        </nav>
      </div>
    </header>
  )
}
