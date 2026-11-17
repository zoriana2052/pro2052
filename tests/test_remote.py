import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import remote_control as r

class RemoteTests(unittest.TestCase):
    def test_catalog_unique_and_all_fixed_commands(self):
        self.assertEqual(len(r.ACTIONS),len(r.BY_ID))
        for a in r.ACTIONS:
            if not a.pattern:self.assertEqual(r.build(a.id),a.prefix)
        self.assertEqual(len([a for a in r.ACTIONS if a.category=='keys']),15)
        expected={'MD','MA','SQ','DL','DS','LO','PR','QU','RI','RM','SB','LL','LU','IC','ID','AF','BT','FI','MU?','MU','RG','SI','TB','TD'}
        self.assertEqual({a.prefix for a in r.ACTIONS if a.id.startswith('get_') and not a.pattern},expected)

    def test_parameterized_commands(self):
        pairs={'key_DIGIT':('7','KEY02 7'),'go_channel':('1000','MA000'),'get_channel':('1','PM001'),
               'freq_RF':('435.375','RF04353750'),'freq_LL':('430','LL04300000'),'freq_LU':('440','LU04400000'),
               'freq_SS':('145.8','SS01458000'),'get_skip':('01','SS01'),'get_priority':('C','PC C'),
               'set_priority':('C101','PC C101'),'set_banks':('CG','SB CG'),'set_ic':('A','IC A'),
               'get_il':('001','IL001'),'il_type1':('012-03','ILR 012-03'),'il_type2':('000016','ILR 000016'),
               'il_edacs':('01-023','ILR 01-023'),'fleet':('A 0 12','FB A 0 12'),'get_pi':('1','PI 1'),
               'set_pi':('101','PI 101'),'set_rg':('01-02','RG 01-02'),
               'talkgroup':('1 1010 01-01','TG 1 1010 01-01'),'trunk_bank':('A 1 04060000 0125','TR A 1 04060000 0125')}
        for id,(value,command) in pairs.items():
            with self.subTest(id=id):self.assertEqual(r.build(id,value),command)
        self.assertEqual({a.id for a in r.ACTIONS if a.pattern},set(pairs))

    def test_injection_and_ranges(self):
        for id,param in [('key_DIGIT','1\rAC'),('go_channel','1001'),('set_banks','AA'),('set_priority','Z000'),('fleet','A 1 12'),('fleet','A 2 13'),('fleet','A 4 14'),('talkgroup','21 111 01-01'),('trunk_bank','A 1 99999999 0125'),('get_skip','123'),('get_MD','AC')]:
            with self.subTest(id=id),self.assertRaises((ValueError,Exception)):r.build(id,param)

    def test_reset_requires_confirmation_before_io(self):
        with patch('remote_control.exchange') as send:
            with self.assertRaises(ValueError):r.execute(None,'reset','','log','COM5',19200)
            send.assert_not_called()

    def test_rejection_timeout_echo_never_retries(self):
        for raw in (b'',b'NG\r',b'ERR\r',b'ORER\r',b'PRN\r'):
            with patch('remote_control.exchange',return_value=raw) as send:
                result=r.execute(None,'PRN','','log','COM5',19200)
                self.assertEqual(result,[('PRN',raw)]);self.assertEqual(send.call_count,1)

    def test_setting_readback_is_separate(self):
        with patch('remote_control.exchange',side_effect=[b'OK\r',b'PRN\r']) as send:
            self.assertEqual(r.execute(None,'PRN','','log','COM5',19200),[('PRN',b'OK\r'),('PR',b'PRN\r')])
            self.assertEqual([x.args[1] for x in send.call_args_list],['PRN','PR'])

    def test_ui_keyboard_and_reset_cancel_do_not_send(self):
        import tkinter as tk
        import window
        import inventory
        import programming
        root=tk.Tk();root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder,patch.object(window.App,'refresh'):
                app=window.App(root,Path(folder));app.port.set('COM5');app.baud.set('19200')
                with patch.object(app.programming,'launch') as send:
                    app.remote.send('key_SCAN');self.assertEqual(send.call_args.args[0],'remote')
                    self.assertEqual(send.call_args.args[2]['id'],'key_SCAN')
                with patch('remote_ui.messagebox.askyesno',return_value=False),patch.object(app.programming,'launch') as send:
                    app.remote.send('key_ENTER');send.assert_not_called()
                app.programming.inventory=inventory.Inventory('COM5',19200,True,{n:programming.Channel(n,'00000000',b'F00000000\r') for n in range(1000)})
                with patch('remote_ui.simpledialog.askstring',return_value=None),patch.object(app.programming,'launch') as send:
                    app.remote.send('reset');send.assert_not_called()
                app.language_ui.language='en';app.language_ui.apply()
                self.assertEqual(app.notebook.tab(app.remote.frame,'text'),'Controls and settings')
        finally:root.destroy()

if __name__=='__main__':unittest.main()
