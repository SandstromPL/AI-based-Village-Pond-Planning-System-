export default function Header({ theme, onToggleTheme }) {
  const isLight = theme === 'light'

  return (
    <header className="app-header">
      <div className="app-header__title">
        <h1>Village Pond Planner</h1>
        <p>Terrain-aware pond site recommendations</p>
      </div>

      <label className="theme-switch" title="Toggle light/dark theme">
        <span className="theme-switch__label">{isLight ? 'Light' : 'Dark'}</span>
        <span className="theme-switch__control">
          <input
            type="checkbox"
            checked={isLight}
            onChange={onToggleTheme}
            aria-label="Toggle light theme"
          />
          <span className="theme-switch__track">
            <span className="theme-switch__thumb" />
          </span>
        </span>
      </label>
    </header>
  )
}
