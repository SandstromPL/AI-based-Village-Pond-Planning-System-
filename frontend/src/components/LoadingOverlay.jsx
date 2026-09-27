export default function LoadingOverlay({ message }) {
  return (
    <div className="loading-overlay" role="status" aria-live="polite">
      <div className="loading-overlay__card">
        <div className="loading-overlay__spinner" />
        <p>{message}</p>
      </div>
    </div>
  )
}
