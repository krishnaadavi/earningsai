export const metadata = {
  title: 'Earnings AI',
  description: 'Upload earnings PDFs and ask questions with citations',
};

import './globals.css';
import Header from './components/Header';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        <div style={{ paddingTop: 8 }}>{children}</div>
      </body>
    </html>
  );
}
