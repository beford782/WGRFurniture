// Central DreamFinder lead backup inbox. Every retailer deployment BCCs this
// address by default so leads roll up centrally. During Apps Script setup,
// review this value:
//   - keep the default to participate in the central backup
//   - replace with a retailer-specific backup inbox if appropriate
//   - set to '' to disable BCC for this deployment
var RESULT_EMAIL_BCC = 'dreamfinderleads@gmail.com';

// Helper: escape five HTML metacharacters; safe for attribute values and text content.
function _escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(ch) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
  });
}

// Helper: permissive email shape check; not full RFC 5322. Catches empty / missing-@ / obvious typos.
function _isValidEmail(s) {
  if (typeof s !== 'string') return false;
  var t = s.trim();
  if (t.length < 3 || t.length > 254) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t);
}

// Helper: restrict to supported languages; default to 'en'.
function _normalizeLang(s) {
  return s === 'es' ? 'es' : 'en';
}

// Helper: coerce + bound length only. Does NOT strip characters (accents, apostrophes, hyphens, Spanish chars).
function _safeText(s, max) {
  if (s == null) return '';
  var str = String(s);
  if (max && str.length > max) str = str.slice(0, max);
  return str;
}

// Helper: allow https:// URLs and repo-relative images/ paths only. Empty otherwise (existing fallback block renders).
function _safeImageUrl(url) {
  if (typeof url !== 'string') return '';
  var t = url.trim();
  if (!t) return '';
  if (/^https:\/\//i.test(t)) return t;
  if (/^images\//.test(t)) return t;
  return '';
}

// Helper: coerce to array; returns [] for non-array inputs.
function _safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    // Shape-only summary; full PII (email/name/phone) shouldn't persist in GAS logs.
    Logger.log('doPost received: name_len=' + (data.name ? String(data.name).length : 0)
      + ', email=' + (data.email ? 'set' : 'unset')
      + ', phone=' + (data.phone ? 'set' : 'unset')
      + ', matches=' + ((data.allMatches || []).length)
      + ', accessories=' + ((data.accessories || []).length)
      + ', lang=' + (data.lang || ''));

    var lang = _normalizeLang(data.lang);
    var isEs = lang === 'es';

    var email = (data.email || '').toString().trim();
    if (!_isValidEmail(email)) {
      Logger.log('doPost rejected: invalid_email');
      return ContentService
        .createTextOutput(JSON.stringify({ success: false, error: 'invalid_email' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // Bound client-controlled scalars defensively.
    var name = _safeText(data.name, 200);
    var phone = _safeText(data.phone, 40);
    var dreamCode = _safeText(data.dreamCode, 40);
    var sleepProfile = _safeText(data.sleepProfile, 500);
    var topMatch = _safeText(data.topMatch, 200);
    var matchPct = _safeText(data.matchPct, 10);
    var rsa = _safeText(data.rsa, 100);
    var discount = _safeText(data.discount || 5, 10);

    // White-label store identity, supplied by the client from STORE_CONFIG.storeName.
    // Falls back to a generic phrase so a missing/blank field never leaks another
    // retailer's name. Used below in plain-text contexts (subject / sender / plain
    // fallback body) with NO HTML escaping; buildSimpleHtml re-escapes for HTML.
    var storeName = _safeText(data.storeName, 100).trim() || (isEs ? 'nuestra tienda' : 'our store');

    // --- Log to Google Sheet ---
    // rsa appended at the end (right-of-last column) per the
    // append-don't-insert strategy documented in docs/gas-rsa-field-addition.md.
    // Inserting mid-row would force every other column to re-index. Sheet
    // operator must add a corresponding "rsa" column header to match.
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    sheet.appendRow([
      new Date(),
      name,
      email,
      phone,
      dreamCode,
      lang,
      _safeArray(data.allMatches).slice(0, 6).map(function(m) { return _safeText(m && m.name, 200) + ' (' + _safeText(m && m.matchPct, 10) + '%)'; }).join(', '),
      _safeArray(data.accessories).slice(0, 3).map(function(a) { return _safeText(a && a.name, 200); }).join(', '),
      rsa
    ]);

    // --- Send email with fallback ---
    var subject = isEs
      ? 'Tu Pase de Ahorro DreamFinder de ' + storeName
      : 'Your DreamFinder Savings Pass from ' + storeName;
    var senderName = isEs
      ? 'Equipo de Descanso de ' + storeName
      : storeName + ' Sleep Team';
    var firstName = (name || (isEs ? 'amigo' : 'there')).split(' ')[0];

    // Pre-bound payload for buildSimpleHtml; image URLs filtered to https:// or images/ only.
    var safeData = {
      dreamCode: dreamCode,
      sleepProfile: sleepProfile,
      topMatch: topMatch,
      matchPct: matchPct,
      discount: discount,
      rsa: rsa,
      allMatches: _safeArray(data.allMatches).slice(0, 6).map(function(m) {
        return {
          name: _safeText(m && m.name, 200),
          brand: _safeText(m && m.brand, 100),
          matchPct: _safeText(m && m.matchPct, 10),
          imageUrl: _safeImageUrl(m && m.imageUrl)
        };
      }),
      accessories: _safeArray(data.accessories).slice(0, 3).map(function(a) {
        return {
          name: _safeText(a && a.name, 200),
          category: _safeText(a && a.category, 100),
          imageUrl: _safeImageUrl(a && a.imageUrl)
        };
      })
    };

    try {
      // Always build HTML server-side. Client previously sent data.htmlBody but
      // that path was deprecated in 5e — kiosk no longer ships pre-built HTML.
      var htmlBody = buildSimpleHtml(safeData, firstName, isEs, storeName);
      var plainFallback = isEs
        ? 'Por favor visualiza este correo en un cliente de correo HTML.'
        : 'Please view in an HTML email client.';

      var mailOptions = {
        htmlBody: htmlBody,
        name: senderName
      };
      if (RESULT_EMAIL_BCC) mailOptions.bcc = RESULT_EMAIL_BCC;
      GmailApp.sendEmail(email, subject, plainFallback, mailOptions);

    } catch (emailErr) {
      Logger.log('HTML email failed, trying plain text: ' + emailErr.toString());
      var plainBody = isEs
        ? ('Hola ' + firstName + ',\n\n'
          + 'Tu mejor opci\u00f3n: ' + topMatch + ' (' + matchPct + '% compatibilidad)\n'
          + 'Perfil de sue\u00f1o: ' + sleepProfile + '\n'
          + 'Tu pase de ahorro: ' + discount + '% DE DESCUENTO\n'
          + 'C\u00f3digo del pase: ' + dreamCode + '\n\n'
          + 'Muestra este correo en ' + storeName + ' para canjearlo.\n\n'
          + safeData.allMatches.map(function(m, i) { return (i+1) + '. ' + m.name + ' - ' + m.matchPct + '% compatibilidad'; }).join('\n'))
        : ('Hi ' + firstName + ',\n\n'
          + 'Your top match: ' + topMatch + ' (' + matchPct + '% match)\n'
          + 'Sleep profile: ' + sleepProfile + '\n'
          + 'Your savings pass: ' + discount + '% OFF\n'
          + 'Savings pass code: ' + dreamCode + '\n\n'
          + 'Show this email at ' + storeName + ' to redeem.\n\n'
          + safeData.allMatches.map(function(m, i) { return (i+1) + '. ' + m.name + ' - ' + m.matchPct + '% match'; }).join('\n'));

      var fallbackOptions = {
        name: senderName
      };
      if (RESULT_EMAIL_BCC) fallbackOptions.bcc = RESULT_EMAIL_BCC;
      GmailApp.sendEmail(email, subject, plainBody, fallbackOptions);
    }

    return ContentService
      .createTextOutput(JSON.stringify({ success: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    // Generic error to browser; full detail stays in GAS logs.
    Logger.log('doPost error: ' + err.toString());
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: 'send_failed' }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function buildSimpleHtml(data, firstName, isEs, storeName) {
  // All user/client-controlled fields below are HTML-escaped at every
  // interpolation site (caller has already _safeText-bounded scalars and
  // _safeImageUrl-filtered image URLs).
  firstName = _escapeHtml(firstName);
  storeName = _escapeHtml(storeName || (isEs ? 'nuestra tienda' : 'our store'));
  var dreamCode = _escapeHtml(data.dreamCode || '');
  // Cap at whatever kiosk sent (kiosk already pre-slices: 6 if saved, 3 if recommendations).
  // Hard ceiling of 6 as a server-side safety net.
  var matches = _safeArray(data.allMatches).slice(0, 6);
  var accs = _safeArray(data.accessories).slice(0, 3);
  var discount = _escapeHtml(data.discount || 5);
  var sleepProfile = _escapeHtml(data.sleepProfile || '');

  var rsa = _escapeHtml((data.rsa || '').toString().trim());

  // Nocturnal palette \u2014 exact hex from index.html :root
  var c = {
    bg: '#14171C',
    surface: '#1A1E25',
    surfaceAlt: '#262A32',
    border: '#3A3E45',
    text: '#F5EFE4',
    textMuted: '#A8A39A',
    textSubtle: '#8A8578',
    accent: '#B8935D',
    accentHover: '#C9A573',
    pageBg: '#0D0F12'
  };

  var serif = "Georgia, 'Times New Roman', serif";
  var sans = "-apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

  // Localized strings
  var L = isEs ? {
    eyebrow: 'TUS RESULTADOS',
    titlePrefix: 'Tus',
    titleAccent: 'combinaciones perfectas',
    titleSuffix: 'est\u00e1n listas, ' + firstName,
    discountLabel: 'TU PASE DE AHORRO',
    discountHint: 'Presenta este c\u00f3digo en ' + storeName + ' \u00b7 ' + discount + '% DE DESCUENTO',
    profileLabel: 'TU PERFIL DE SUE\u00d1O',
    matchesLabel: 'TUS MEJORES OPCIONES',
    topPick: 'MEJOR OPCI\u00d3N',
    matchSuffix: 'compatibilidad',
    accLabel: 'ACCESORIOS RECOMENDADOS',
    footerLine1: 'Lleva este correo a tu tienda ' + storeName,
    helpedBy: rsa ? 'Atendido por ' + rsa + ' en ' + storeName : '',
    footerLine2: 'Tu ' + discount + '% de descuento te est\u00e1 esperando',
    footerHint: 'Disponible en cualquier tienda ' + storeName
  } : {
    eyebrow: 'YOUR RESULTS',
    titlePrefix: 'Your',
    titleAccent: 'perfect matches',
    titleSuffix: 'are ready, ' + firstName,
    discountLabel: 'YOUR SAVINGS PASS',
    discountHint: 'Show at ' + storeName + ' \u00b7 ' + discount + '% OFF',
    profileLabel: 'YOUR SLEEP PROFILE',
    matchesLabel: 'YOUR TOP MATCHES',
    topPick: 'TOP PICK',
    matchSuffix: 'match',
    accLabel: 'RECOMMENDED ACCESSORIES',
    footerLine1: 'Bring this email to your ' + storeName + ' store',
    helpedBy: rsa ? 'Helped by ' + rsa + ' at ' + storeName : '',
    footerLine2: 'Your ' + discount + '% discount is waiting',
    footerHint: 'Show at any ' + storeName + ' location'
  };

  // Helper: mattress card with image-blocked fallback
  function mattressCard(m, isTop) {
    var name = _escapeHtml(m.name || '');
    var brand = _escapeHtml(m.brand || '');
    var pct = _escapeHtml(m.matchPct || '');
    var img = _escapeHtml(m.imageUrl || '');
    var rankBlock = isTop
      ? '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:6px;">' + L.topPick + '</div>'
      : '';
    // Image with bulletproof fallback \u2014 if blocked, the cell shows a surface tile with mattress name
    var imgCell = '<td width="90" valign="top" style="padding:0;background:' + c.surface + ';border-right:1px solid ' + c.border + ';">'
      + (img
          ? '<img src="' + img + '" width="90" height="80" alt="' + name + '" style="display:block;border:0;width:90px;height:80px;object-fit:cover;background:' + c.surface + ';">'
          : '<div style="width:90px;height:80px;background:' + c.surface + ';"></div>')
      + '</td>';
    return ''
      + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';margin-bottom:10px;border-radius:2px;">'
      + '<tr>'
      + imgCell
      + '<td valign="middle" style="padding:14px 18px;">'
      + rankBlock
      + '<div style="font-family:' + serif + ';font-size:18px;color:' + c.text + ';font-weight:normal;line-height:1.2;margin-bottom:4px;">' + name + '</div>'
      + '<div style="font-family:' + sans + ';font-size:12px;color:' + c.textMuted + ';margin-bottom:6px;">' + brand + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;">' + pct + '% ' + L.matchSuffix + '</div>'
      + '</td>'
      + '</tr>'
      + '</table>';
  }

  var matchRows = matches.map(function(m, i) { return mattressCard(m, i === 0); }).join('');

  // Accessories \u2014 single column rows, not 3-up grid (Outlook table-cell math is unreliable)
  var accRows = accs.map(function(a) {
    var name = _escapeHtml(a.name || '');
    var category = _escapeHtml(a.category || '');
    var img = _escapeHtml(a.imageUrl || '');
    return ''
      + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';margin-bottom:8px;border-radius:2px;">'
      + '<tr>'
      + '<td width="60" valign="middle" style="padding:0;background:' + c.surface + ';">'
      + (img
          ? '<img src="' + img + '" width="60" height="60" alt="' + name + '" style="display:block;border:0;width:60px;height:60px;object-fit:cover;">'
          : '<div style="width:60px;height:60px;background:' + c.surface + ';"></div>')
      + '</td>'
      + '<td valign="middle" style="padding:10px 14px;">'
      + '<div style="font-family:' + serif + ';font-size:14px;color:' + c.text + ';line-height:1.2;">' + name + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1.5px;color:' + c.textSubtle + ';text-transform:uppercase;margin-top:3px;">' + category + '</div>'
      + '</td>'
      + '</tr>'
      + '</table>';
  }).join('');

  var accSection = accs.length > 0
    ? '<tr><td style="padding:8px 32px 24px;">'
      + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:14px;">' + L.accLabel + '</div>'
      + accRows
      + '</td></tr>'
    : '';

  return ''
    + '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    + '<html xmlns="http://www.w3.org/1999/xhtml">'
    + '<head>'
    + '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<title>DreamFinder Results</title>'
    + '<!--[if mso]><style>td,div,p,a {font-family: Georgia, "Times New Roman", serif !important;}</style><![endif]-->'
    + '</head>'
    + '<body style="margin:0;padding:0;background:' + c.pageBg + ';">'
    + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.pageBg + ';">'
    + '<tr><td align="center" style="padding:24px 12px;">'
    + '<table width="600" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.bg + ';max-width:600px;width:100%;">'

    // Header \u2014 eyebrow + serif headline
    + '<tr><td style="padding:36px 32px 28px;text-align:center;border-bottom:1px solid ' + c.border + ';">'
    + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:3px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:14px;">' + L.eyebrow + '</div>'
    + '<div style="font-family:' + serif + ';font-size:28px;line-height:1.25;color:' + c.text + ';font-weight:normal;">'
    + L.titlePrefix + ' <em style="color:' + c.accent + ';font-style:italic;">' + L.titleAccent + '</em> ' + L.titleSuffix
    + '</div>'
    + '</td></tr>'

    // DREAM hero band \u2014 full width, brass-tinted background
    + (dreamCode
        ? '<tr><td style="background:' + c.surfaceAlt + ';border-bottom:1px solid ' + c.border + ';padding:32px;text-align:center;">'
          + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:3px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:14px;">' + L.discountLabel + '</div>'
          + '<div style="font-family:' + serif + ';font-size:36px;letter-spacing:6px;color:' + c.accent + ';line-height:1;margin-bottom:12px;">' + dreamCode + '</div>'
          + '<div style="font-family:' + sans + ';font-size:12px;color:' + c.textMuted + ';">' + L.discountHint + '</div>'
          + '</td></tr>'
        : '')

    // Sleep profile
    + (sleepProfile
        ? '<tr><td style="padding:28px 32px 16px;">'
          + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:8px;">' + L.profileLabel + '</div>'
          + '<div style="font-family:' + serif + ';font-size:18px;color:' + c.text + ';line-height:1.3;">' + sleepProfile + '</div>'
          + '</td></tr>'
        : '')

    // Mattress matches
    + '<tr><td style="padding:16px 32px 8px;">'
    + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:14px;">' + L.matchesLabel + '</div>'
    + matchRows
    + '</td></tr>'

    // Accessories (conditional)
    + accSection

    // Footer
    + '<tr><td style="padding:24px 32px 36px;text-align:center;border-top:1px solid ' + c.border + ';">'
    + '<div style="font-family:' + sans + ';font-size:13px;color:' + c.textMuted + ';margin-bottom:8px;">' + L.footerLine1 + '</div>'
    + (L.helpedBy ? '<div style="font-family:' + sans + ';font-size:13px;color:' + c.textMuted + ';margin-bottom:8px;">' + L.helpedBy + '</div>' : '')
    + '<div style="font-family:' + serif + ';font-size:18px;color:' + c.accent + ';font-style:italic;line-height:1.3;">' + L.footerLine2 + '</div>'
    + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1.5px;color:' + c.textSubtle + ';text-transform:uppercase;margin-top:14px;">' + L.footerHint + '</div>'
    + '</td></tr>'

    + '</table>'
    + '</td></tr></table>'
    + '</body></html>';
}
