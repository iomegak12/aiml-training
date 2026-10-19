import ChatSidebar from '../components/chat/ChatSidebar'
import ChatWindow from '../components/chat/ChatWindow'
import { useChat } from '../hooks/useChat'
import styles from './SupportPage.module.css'

export default function SupportPage() {
  const chat = useChat()

  return (
    <div className={styles.page}>
      <ChatSidebar
        sessions={chat.sessions}
        activeId={chat.activeSession?.id}
        onSelect={chat.selectSession}
        onNewChat={chat.newChat}
      />
      <ChatWindow chat={chat} />
    </div>
  )
}
