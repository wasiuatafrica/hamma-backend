const React = require('react');
const { useEffect, useState } = require('react');
const { w3cwebsocket: W3CWebSocket } = require('websocket');
const { useCookies } = require('react-cookie');

const WebSocketComponent = () => {
  // Assuming you manually pass the access token as a prop or variable
  const manuallyPassedAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzAzMTcxMjc0LCJpYXQiOjE3MDE4NzUyNzQsImp0aSI6IjlkOTUzYWRhZDljMzQ1ODJhNmIxNzQ5Yzk5MTU1MGViIiwidXNlcl9pZCI6MX0.Dtk9JCm8TcGca5OJyxN3_jwJMKj8Lm-PvTtPGnbbdi8';

  const [socket, setSocket] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    if (manuallyPassedAccessToken) {
      const ws = new W3CWebSocket(`ws://127.0.0.1/ws/notifications/`, null, {
        headers: {
          Authorization: `Bearer ${manuallyPassedAccessToken}`,
        },
      });

      ws.onopen = () => {
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data.message);

        // Update the messages state with the received message
        setMessages((prevMessages) => [...prevMessages, data.message]);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
      };

      setSocket(ws);
    }

    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [manuallyPassedAccessToken, socket]);

  const handleItemClick = (notificationId) => {
    // Handle the click on the message item (e.g., send notification ID)
    console.log('Notification ID clicked:', notificationId);
    // Add your logic to handle the notification ID as needed
  };

  return (
    <div>
      <h1>WebSocket Messages</h1>
      <ul>
        {messages.map((message, index) => (
          <li key={index} onClick={() => handleItemClick(message.notification_id)}>
            {message.text}
          </li>
        ))}
      </ul>
    </div>
  );
};

module.exports = WebSocketComponent;
