import base64
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = 'stock.move'

    serial_numbers_file = fields.Binary(
        filters='*.csv',
    )

    #@api.constrains('move_line_ids')
    #def _check_move_line_ids(self):
    #    type = self.picking_id.picking_type_id.code
    #    for line in self.move_line_ids:
    #        if (type == 'incoming' and not line.lot_name) or (type == 'outgoing' and not line.lot_id) or not line.qty_done:
    #            raise ValidationError(_("All serial numbers and quantities must be placed"))

    def _create_lines(self, serial_numbers):
        while len(self.move_line_ids) < len(serial_numbers):
            self.env['stock.move.line'].create({
                'location_dest_id': self.location_dest_id.id,
                'location_id': self.location_id.id,
                'move_id': self.id,
                'product_id': self.product_id.id,
                'product_uom_id': self.product_uom.id,
                'product_uom_qty': 0,
                'qty_done': 1,
            })

    @api.multi
    def action_load_serial_numbers(self):
        self.ensure_one()
        # Validations
        if not self.serial_numbers_file:
            raise ValidationError(_('File not selected'))
        file_content = base64.decodestring(self.serial_numbers_file).decode('utf-8')
        serial_numbers_list = file_content.splitlines()
        if len(serial_numbers_list) < 2:
            raise ValidationError(_('No serial numbers in file'))
        serial_numbers_list.pop(0)  # Remove header
        serial_numbers = set(serial_numbers_list)
        if len(serial_numbers_list) > len(serial_numbers):
            raise ValidationError(_('Serial numbers must be unique'))
        # Purchases
        if self.picking_id.picking_type_id.code == 'incoming':
            stock = self.env['stock.production.lot'].search([('product_id', '=', self.product_id.id)])
            serial_numbers_used = set(lot.name for lot in stock)
            if serial_numbers & serial_numbers_used:
                raise ValidationError(_('Serial numbers already used: ' + str(serial_numbers & serial_numbers_used)))
            self._create_lines(serial_numbers)
            for serial_number, line in zip(serial_numbers_list, self.move_line_ids):
                line.lot_name = serial_number
                line.qty_done = 1
        # Sales
        elif self.picking_id.picking_type_id.code == 'outgoing':
            stock = self.env['stock.quant'].search([
                ('location_id.usage', '=', 'internal'),
                ('product_id', '=', self.product_id.id),
                ('quantity', '=', 1),
                ('reserved_quantity', '=', 0),
            ])
            serial_numbers_available = set(lot.lot_id.name for lot in stock)
            if not serial_numbers <= serial_numbers_available:
                raise ValidationError(_('Serial numbers not available: ' + str(serial_numbers - serial_numbers_available)))
            self._create_lines(serial_numbers)
            for serial_number, line in zip(serial_numbers_list, self.move_line_ids):
                line.lot_id = self.env['stock.production.lot'].search([('name', '=', serial_number)], limit=1)
                line.qty_done = 1
            # Asign move lines to picking
            self.picking_id.move_line_ids = self.move_line_ids
        # Remove file content to free up space
        self.serial_numbers_file = ''
        return {
            "type": "ir.actions.do_nothing",
        }
