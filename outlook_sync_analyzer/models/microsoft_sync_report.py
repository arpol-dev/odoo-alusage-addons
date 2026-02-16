# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import re
import base64


class MicrosoftSyncReport(models.Model):
    _name = 'microsoft.sync.report'
    _description = 'Rapport de synchronisation Microsoft Calendar'
    _order = 'create_date desc'

    name = fields.Char('Nom', compute='_compute_name', store=True)
    log_id = fields.Many2one('microsoft.sync.log', string='Log', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Utilisateur', required=True, related='log_id.user_id', store=True)
    content = fields.Text('Contenu Markdown', required=True)
    content_html = fields.Html('Contenu HTML')
    attachment_id = fields.Many2one('ir.attachment', string='Fichier rapport', readonly=True)

    @api.depends('log_id', 'create_date')
    def _compute_name(self):
        for report in self:
            date_str = fields.Datetime.to_string(report.create_date or fields.Datetime.now())
            operation = dict(report.log_id._fields['operation'].selection).get(report.log_id.operation, 'sync')
            report.name = f"{date_str} - {operation} - {report.user_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate HTML from markdown if not provided"""
        for vals in vals_list:
            if vals.get('content') and not vals.get('content_html'):
                vals['content_html'] = self._markdown_to_html(vals['content'])
        return super().create(vals_list)

    def write(self, vals):
        """Auto-update HTML when markdown changes"""
        if 'content' in vals and 'content_html' not in vals:
            vals['content_html'] = self._markdown_to_html(vals['content'])
        return super().write(vals)

    def _markdown_to_html(self, markdown_text):
        """Convert simple markdown to HTML"""
        if not markdown_text:
            return ''

        html = markdown_text

        # Headers
        html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)

        # Lists
        html = re.sub(r'^\- (.*?)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*?</li>\n)+', r'<ul>\g<0></ul>', html, flags=re.DOTALL)

        # Tables
        lines = html.split('\n')
        in_table = False
        result = []

        for i, line in enumerate(lines):
            if '|' in line and not line.strip().startswith('<'):
                if not in_table:
                    result.append('<table class="table table-sm table-striped">')
                    in_table = True

                cells = [cell.strip() for cell in line.split('|')[1:-1]]

                # Skip separator line
                if all(set(cell.replace('-', '').strip()) == set() for cell in cells):
                    continue

                # Check if header (next line is separator)
                is_header = i + 1 < len(lines) and all('-' in c for c in lines[i + 1].split('|')[1:-1])

                if is_header:
                    result.append('<thead><tr>')
                    result.append(''.join(f'<th>{cell}</th>' for cell in cells))
                    result.append('</tr></thead><tbody>')
                else:
                    result.append('<tr>')
                    result.append(''.join(f'<td>{cell}</td>' for cell in cells))
                    result.append('</tr>')
            else:
                if in_table:
                    result.append('</tbody></table>')
                    in_table = False
                result.append(line)

        if in_table:
            result.append('</tbody></table>')

        html = '\n'.join(result)

        # Paragraphs
        html = re.sub(r'\n\n', r'</p><p>', html)
        html = f'<div class="o_outlook_sync_report"><p>{html}</p></div>'

        return html

    def action_download_report(self):
        """Télécharge le rapport markdown"""
        self.ensure_one()

        # Crée l'attachment s'il n'existe pas
        if not self.attachment_id:
            timestamp = fields.Datetime.to_string(self.create_date).replace(' ', '_').replace(':', '-')
            filename = f"sync_report_{self.user_id.login}_{timestamp}.md"

            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(self.content.encode('utf-8')),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'text/markdown',
            })
            self.attachment_id = attachment.id

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'self',
        }
