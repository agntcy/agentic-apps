import React from "react"

const HeadlineItem = ({ title, summary, submolt, onClick }) => {
  const content = (
    <>
      {submolt && <div className="headline-submolt">m/{submolt}</div>}
      <div className="headline-title">{title}</div>
      <div className="headline-summary">{summary}</div>
      <div className="headline-divider" />
    </>
  )

  return (
    <button
      className="headline-item headline-button"
      type="button"
      onClick={onClick}
    >
      {content}
    </button>
  )
}

export default HeadlineItem
