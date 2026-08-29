// ==UserScript==
// @name         Cabanga - Capture refresh_token
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  Affiche automatiquement le refresh_token Cabanga après connexion, pour l'intégration Home Assistant
// @match        https://app.cabanga.be/*
// @match        https://login.scolares.be/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  console.log('[Cabanga capture] script chargé sur', window.location.href);

  function handleTokenResponse(data) {
    if (data && data.refresh_token) {
      console.log('[Cabanga capture] refresh_token détecté !');
      const joursValidite = Math.round((data.refresh_expires_in || 0) / 86400);
      const message =
        'Refresh token Cabanga capturé — copie-le (Cmd+A puis Cmd+C) :\n\n' +
        'Expire dans : ' + joursValidite + ' jour(s)\n';
      window.prompt(message, data.refresh_token);
    }
  }

  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    return originalFetch.apply(this, args).then((response) => {
      const url = args[0] ? args[0].toString() : '';
      if (url.includes('/protocol/openid-connect/token')) {
        console.log('[Cabanga capture] requête token détectée via fetch:', url);
        response
          .clone()
          .json()
          .then(handleTokenResponse)
          .catch((e) => console.log('[Cabanga capture] erreur parsing fetch:', e));
      }
      return response;
    });
  };

  const OriginalXHR = window.XMLHttpRequest;
  function PatchedXHR() {
    const xhr = new OriginalXHR();
    const originalOpen = xhr.open;
    let requestUrl = '';

    xhr.open = function (method, url, ...rest) {
      requestUrl = url ? url.toString() : '';
      return originalOpen.call(xhr, method, url, ...rest);
    };

    xhr.addEventListener('load', function () {
      if (requestUrl.includes('/protocol/openid-connect/token')) {
        console.log('[Cabanga capture] requête token détectée via XHR:', requestUrl);
        try {
          const data = JSON.parse(xhr.responseText);
          handleTokenResponse(data);
        } catch (e) {
          console.log('[Cabanga capture] erreur parsing XHR:', e);
        }
      }
    });

    return xhr;
  }
  window.XMLHttpRequest = PatchedXHR;
})();
