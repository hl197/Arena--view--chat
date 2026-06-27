import { Link } from 'react-router-dom'

export default function Header() {
  return (
    <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-lg font-bold">
          <span className="text-arena-500">⚔️</span>
          <span>ArenaView</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm text-gray-400">
          <Link to="/history" className="hover:text-gray-200 transition-colors">历史</Link>
          <Link to="/settings" className="hover:text-gray-200 transition-colors">
            <span className="text-gray-500">⚙️</span> API
          </Link>
        </nav>
      </div>
    </header>
  )
}
