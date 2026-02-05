/**
 * i18n 国际化配置
 * 
 * 使用 react-i18next 进行国际化支持
 * 默认语言：中文
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zhCN from './locales/zh-CN.json';
import enUS from './locales/en-US.json';

// 检测浏览器语言，但默认使用中文
const getDefaultLanguage = (): string => {
  // 可以从 VSCode 配置中读取语言设置，这里先默认使用中文
  // 尝试从 URL 参数或 localStorage 读取语言设置
  const urlParams = new URLSearchParams(window.location.search);
  const langParam = urlParams.get('lang');
  if (langParam === 'en-US' || langParam === 'en') {
    return 'en-US';
  }
  return 'zh-CN';
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      'zh-CN': {
        translation: zhCN,
      },
      'en-US': {
        translation: enUS,
      },
    },
    lng: getDefaultLanguage(), // 默认语言：中文
    fallbackLng: 'zh-CN', // 回退语言：中文
    interpolation: {
      escapeValue: false, // React 已经转义了
    },
  });

export default i18n;

