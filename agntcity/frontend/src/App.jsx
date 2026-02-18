import React, { useEffect, useState } from "react"
import HeadlineItem from "./components/HeadlineItem.jsx"
import articlesData from "./data/articles.json"

const App = () => {
  const [status, setStatus] = useState("idle")
  const [detail, setDetail] = useState("")
  const [selectedArticle, setSelectedArticle] = useState(null)
  const apiBase =
    import.meta.env.VITE_NEWS_APP_API_URL || "http://127.0.0.1:8001"
  const slugify = (value) =>
    value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")

  const articles = Object.values(articlesData.articles).map((article) => ({
    ...article,
    slug: slugify(article.title),
  }))
  const leftArticles = articles.slice(0, 3)
  const extraArticles = Array.from({ length: 4 }, (_, index) => {
    return articles[index % articles.length]
  })
  const openArticleInNewTab = (article) => {
    const url = `${window.location.origin}/article/${article.slug}`
    window.open(url, "_blank", "noopener,noreferrer")
  }
  const handleBackToList = () => {
    setSelectedArticle(null)
  }
  const todayLabel = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  })

  const testHealth = async () => {
    try {
      setStatus("loading")
      setDetail("")
      const response = await fetch(`${apiBase}/health`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      setStatus("ok")
      setDetail(JSON.stringify(data))
    } catch (error) {
      setStatus("error")
      setDetail(error?.message || "Unknown error")
    }
  }

  useEffect(() => {
    testHealth()
  }, [])

  useEffect(() => {
    const path = window.location.pathname
    if (path.startsWith("/article/")) {
      const slug = path.replace("/article/", "")
      const match = articles.find((article) => article.slug === slug)
      if (match) {
        setSelectedArticle(match)
      }
    }
  }, [])


  return (
    <div className="app">
      <div className={`content ${selectedArticle ? "article-page" : ""}`}>
        {selectedArticle ? (
          <div className="article-view">
            <div className="article-header">
              <div className="article-date">{todayLabel}</div>
              <div className="article-site-title">Agncity Times</div>
            </div>
            <hr className="article-divider" />
            <button
              type="button"
              className="back-button"
              onClick={handleBackToList}
            >
              ← Back
            </button>
            <div className="article-title">{selectedArticle.title}</div>
            <div className="article-summary">{selectedArticle.summary}</div>
            <div className="article-content">{selectedArticle.content}</div>
          </div>
        ) : (
          <>
            <div className="header">
              <div className="date-box">{todayLabel}</div>
              <div className="title">Agncity Times</div>
              <div className="header-spacer" />
            </div>
            <hr className="divider" />
            <nav className="nav">
              <span>technology</span>
              <span>memes</span>
              <span>ai labs</span>
              <span>model wars</span>
            </nav>
            <div className="split-section">
          <div className="split-left">
            <div className="split-left-content">
              {leftArticles.map((article, index) => (
                <HeadlineItem
                  key={`${article.title}-${index}`}
                  title={article.title}
                  summary={article.summary}
                  onClick={() => openArticleInNewTab(article)}
                />
              ))}
            </div>
            <div className="split-line split-line-inner" />
            <div className="main-headline">
              <img
                className="main-image"
                src="https://images.unsplash.com/photo-1768755457768-f4d561ab158e?q=80&w=2067&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
                alt="Feature"
              />
              {articles[0] ? (
                <HeadlineItem
                  title={articles[0].title}
                  summary={articles[0].summary}
                  onClick={() => openArticleInNewTab(articles[0])}
                />
              ) : null}
            </div>
          </div>
          <div className="split-line split-line-outer" />
          <div className="split-right">
                <img className="right-image" src="https://images.unsplash.com/photo-1496318447583-f524534e9ce1?q=80&w=2134&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"/>
            
            {articles.slice(1, 3).map((article) => (
              <HeadlineItem
                key={`right-${article.title}`}
                title={article.title}
                summary={article.summary}
                onClick={() => openArticleInNewTab(article)}
              />
            ))}
          </div>
        </div>
        <div className="extra-articles">
          {extraArticles.map((article, index) => (
            <HeadlineItem
              key={`extra-${article.title}-${index}`}
              title={article.title}
              summary={article.summary}
              onClick={() => openArticleInNewTab(article)}
            />
          ))}
        </div>
          </>
        )}

        

        
      </div>
    </div>
  )
}

export default App
