import base64
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = 'stock.move'

    serial_numbers_file = fields.Binary(
        filters='*.csv',
    )

    @api.constrains('move_line_ids')
    def _check_move_line_ids(self):
        for line in self.move_line_ids:
            if not (line.lot_id or line.lot_name) or not line.qty_done:
                raise ValidationError(_("All serial numbers and quantities must be placed"))

    @api.multi
    def action_load_serial_numbers(self):
        self.ensure_one()

        if not self.serial_numbers_file:
            raise ValidationError(_('File not selected'))

        file_content = base64.decodestring(
            self.serial_numbers_file).decode('utf-8')

        if len(file_content.splitlines()) < 2:
            raise ValidationError(_('No serial numbers in file'))

        serial_numbers_list = []

        for line in file_content.splitlines()[1:]:
            serial_numbers_list.append(line)

        serial_numbers = set(serial_numbers_list)

        if len(serial_numbers_list) > len(serial_numbers):
            raise ValidationError(_('Serial numbers must be unique'))

        if len(serial_numbers) != self.product_uom_qty:
            raise ValidationError(_('The ammount of Serial numbers must be identical to the Initial Demand'))

        stock = self.env['stock.production.lot'].search(
            [('product_id', '=', self.product_id.id)])

        serial_numbers_used = set(lot.name for lot in stock)

        if serial_numbers & serial_numbers_used:
            raise ValidationError(_('Serial numbers already used: ' + str(serial_numbers & serial_numbers_used)))

        for serial_number, line in zip(serial_numbers_list, self.move_line_ids):
            line.lot_name = serial_number
            line.qty_done = 1

        self.serial_numbers_file = ''  # Remove the contents of the file to free up space

        return {
            "type": "ir.actions.do_nothing",
        }
