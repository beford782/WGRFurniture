function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    Logger.log('Received: ' + JSON.stringify(data));

    var isEs = data.lang === 'es';

    // --- Log to Google Sheet ---
    // rsa appended at the end (right-of-last column) per the
    // append-don't-insert strategy documented in docs/gas-rsa-field-addition.md.
    // Inserting mid-row would force every other column to re-index. Sheet
    // operator must add a corresponding "rsa" column header to match.
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    sheet.appendRow([
      new Date(),
      data.name || '',
      data.email || '',
      data.phone || '',
      data.dreamCode || '',
      data.lang || 'en',
      (data.allMatches || []).map(function(m) { return m.name + ' (' + m.matchPct + '%)'; }).join(', '),
      (data.accessories || []).map(function(a) { return a.name; }).join(', '),
      (data.rsa || '').toString()
    ]);

    // --- Send email with fallback ---
    var toEmail = data.email;
    var subject = isEs
      ? 'Tus Resultados de DreamFinder de Bel Furniture'
      : 'Your DreamFinder Results from Bel Furniture';
    var senderName = isEs
      ? 'Equipo de Descanso de Bel Furniture'
      : 'Bel Furniture Sleep Team';
    var firstName = (data.name || (isEs ? 'amigo' : 'there')).split(' ')[0];

    try {
      // Always build HTML server-side. Client previously sent data.htmlBody but
      // that path was deprecated in 5e — kiosk no longer ships pre-built HTML.
      var htmlBody = buildSimpleHtml(data, firstName, isEs);
      var plainFallback = isEs
        ? 'Por favor visualiza este correo en un cliente de correo HTML.'
        : 'Please view in an HTML email client.';

      GmailApp.sendEmail(toEmail, subject, plainFallback, {
        htmlBody: htmlBody,
        name: senderName,
        bcc: 'dreamfinderleads@gmail.com'
      });

    } catch (emailErr) {
      Logger.log('HTML email failed, trying plain text: ' + emailErr.toString());
      var plainBody = isEs
        ? ('Hola ' + firstName + ',\n\n'
          + 'Tu mejor opci\u00f3n: ' + (data.topMatch || '') + ' (' + (data.matchPct || '') + '% compatibilidad)\n'
          + 'Perfil de sue\u00f1o: ' + (data.sleepProfile || '') + '\n'
          + 'Tu descuento: ' + (data.discount || 5) + '% DE DESCUENTO\n'
          + 'C\u00f3digo de descuento: ' + (data.dreamCode || '') + '\n\n'
          + 'Muestra este correo en Bel Furniture para canjearlo.\n\n'
          + (data.allMatches || []).map(function(m, i) { return (i+1) + '. ' + m.name + ' - ' + m.matchPct + '% compatibilidad'; }).join('\n'))
        : ('Hi ' + firstName + ',\n\n'
          + 'Your top match: ' + (data.topMatch || '') + ' (' + (data.matchPct || '') + '% match)\n'
          + 'Sleep profile: ' + (data.sleepProfile || '') + '\n'
          + 'Your discount: ' + (data.discount || 5) + '% OFF\n'
          + 'Discount code: ' + (data.dreamCode || '') + '\n\n'
          + 'Show this email at Bel Furniture to redeem.\n\n'
          + (data.allMatches || []).map(function(m, i) { return (i+1) + '. ' + m.name + ' - ' + m.matchPct + '% match'; }).join('\n'));

      GmailApp.sendEmail(toEmail, subject, plainBody, {
        name: senderName,
        bcc: 'dreamfinderleads@gmail.com'
      });
    }

    return ContentService
      .createTextOutput(JSON.stringify({ success: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    Logger.log('doPost error: ' + err.toString());
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function buildSimpleHtml(data, firstName, isEs) {
  var dreamCode = data.dreamCode || '';
  // Cap at whatever kiosk sent (kiosk already pre-slices: 6 if saved, 3 if recommendations).
  // Hard ceiling of 6 as a server-side safety net.
  var matches = (data.allMatches || []).slice(0, 6);
  var accs = (data.accessories || []).slice(0, 3);
  var discount = data.discount || 5;
  var sleepProfile = data.sleepProfile || '';

  // Inline HTML escape for the RSA name — it's free-text input via the device
  // picker prompt, more exposed to injection than other interpolated fields
  // (which come from controlled sources: validated form inputs, predefined
  // data files). Following the existing trust-the-client convention for those
  // fields and adding surgical defense only for rsa keeps this commit focused;
  // a broader Code.gs escape audit is a separate concern.
  var rsa = (data.rsa || '').toString().trim().replace(/[&<>"']/g, function(ch) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
  });

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
    discountLabel: 'TU C\u00d3DIGO DE DESCUENTO',
    discountHint: 'Presenta este c\u00f3digo en Bel Furniture \u00b7 ' + discount + '% DE DESCUENTO',
    profileLabel: 'TU PERFIL DE SUE\u00d1O',
    matchesLabel: 'TUS MEJORES OPCIONES',
    topPick: 'MEJOR OPCI\u00d3N',
    matchSuffix: 'compatibilidad',
    accLabel: 'ACCESORIOS RECOMENDADOS',
    footerLine1: 'Lleva este correo a tu tienda Bel Furniture',
    helpedBy: rsa ? 'Atendido por ' + rsa + ' en Bel Furniture' : '',
    footerLine2: 'Tu ' + discount + '% de descuento te est\u00e1 esperando',
    footerHint: 'Sin caducidad \u00b7 Solo en tienda'
  } : {
    eyebrow: 'YOUR RESULTS',
    titlePrefix: 'Your',
    titleAccent: 'perfect matches',
    titleSuffix: 'are ready, ' + firstName,
    discountLabel: 'YOUR DISCOUNT CODE',
    discountHint: 'Show at Bel Furniture \u00b7 ' + discount + '% OFF',
    profileLabel: 'YOUR SLEEP PROFILE',
    matchesLabel: 'YOUR TOP MATCHES',
    topPick: 'TOP PICK',
    matchSuffix: 'match',
    accLabel: 'RECOMMENDED ACCESSORIES',
    footerLine1: 'Bring this email to your Bel Furniture store',
    helpedBy: rsa ? 'Helped by ' + rsa + ' at Bel Furniture' : '',
    footerLine2: 'Your ' + discount + '% discount is waiting',
    footerHint: 'No expiration \u00b7 In-store only'
  };

  // Helper: mattress card with image-blocked fallback
  function mattressCard(m, isTop) {
    var rankBlock = isTop
      ? '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:6px;">' + L.topPick + '</div>'
      : '';
    // Image with bulletproof fallback \u2014 if blocked, the cell shows a surface tile with mattress name
    var imgCell = '<td width="90" valign="top" style="padding:0;background:' + c.surface + ';border-right:1px solid ' + c.border + ';">'
      + (m.imageUrl
          ? '<img src="' + m.imageUrl + '" width="90" height="80" alt="' + m.name + '" style="display:block;border:0;width:90px;height:80px;object-fit:cover;background:' + c.surface + ';">'
          : '<div style="width:90px;height:80px;background:' + c.surface + ';"></div>')
      + '</td>';
    return ''
      + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';margin-bottom:10px;border-radius:2px;">'
      + '<tr>'
      + imgCell
      + '<td valign="middle" style="padding:14px 18px;">'
      + rankBlock
      + '<div style="font-family:' + serif + ';font-size:18px;color:' + c.text + ';font-weight:normal;line-height:1.2;margin-bottom:4px;">' + m.name + '</div>'
      + '<div style="font-family:' + sans + ';font-size:12px;color:' + c.textMuted + ';margin-bottom:6px;">' + (m.brand || '') + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;">' + m.matchPct + '% ' + L.matchSuffix + '</div>'
      + '</td>'
      + '</tr>'
      + '</table>';
  }

  var matchRows = matches.map(function(m, i) { return mattressCard(m, i === 0); }).join('');

  // Accessories \u2014 single column rows, not 3-up grid (Outlook table-cell math is unreliable)
  var accRows = accs.map(function(a) {
    return ''
      + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';margin-bottom:8px;border-radius:2px;">'
      + '<tr>'
      + '<td width="60" valign="middle" style="padding:0;background:' + c.surface + ';">'
      + (a.imageUrl
          ? '<img src="' + a.imageUrl + '" width="60" height="60" alt="' + a.name + '" style="display:block;border:0;width:60px;height:60px;object-fit:cover;">'
          : '<div style="width:60px;height:60px;background:' + c.surface + ';"></div>')
      + '</td>'
      + '<td valign="middle" style="padding:10px 14px;">'
      + '<div style="font-family:' + serif + ';font-size:14px;color:' + c.text + ';line-height:1.2;">' + a.name + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1.5px;color:' + c.textSubtle + ';text-transform:uppercase;margin-top:3px;">' + (a.category || '') + '</div>'
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
