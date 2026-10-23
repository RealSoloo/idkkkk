"""Own-character editor checks with mock R6/R15 parts; no live Roblox execution."""
from pathlib import Path
import unittest
from lupa import LuaRuntime

SOURCE = Path(__file__).resolve().parents[1].joinpath('Soloshub.txt').read_text()
BLOCK = SOURCE.split('-- BODY EDITOR BEGIN:', 1)[1].split('\n', 1)[1].split('-- BODY EDITOR END', 1)[0]
FIXTURE = r'''
math.clamp = function(v,a,b) return math.max(a,math.min(b,v)) end
Vector3 = {new=function(x,y,z) return {X=x,Y=y,Z=z} end}
local CF = {}; CF.__index=CF
function CF.__mul(a,b) return setmetatable({X=a.X+b.X,Y=a.Y+b.Y,Z=a.Z+b.Z,RX=(a.RX or 0)+(b.RX or 0)},CF) end
CFrame={new=function(x,y,z) return setmetatable({X=x or 0,Y=y or 0,Z=z or 0},CF) end,
 Angles=function(x,y,z) return setmetatable({X=0,Y=0,Z=0,RX=x,RY=y,RZ=z},CF) end}
function signal()
 local s={callbacks={}}
 function s:Connect(fn) table.insert(self.callbacks,fn) end
 function s:Fire(...) for _,fn in ipairs(self.callbacks) do fn(...) end end
 return s
end
function node(name,kind,parent)
 local n={Name=name,ClassName=kind,Parent=parent,children={}}
 if parent then table.insert(parent.children,n) end
 function n:IsA(k) return self.ClassName==k or k=='BasePart' and (self.ClassName=='Part' or self.ClassName=='MeshPart') end
 function n:IsDescendantOf(p) local a=self.Parent while a do if a==p then return true end a=a.Parent end return false end
 function n:GetChildren() local out={} for _,c in ipairs(self.children) do if c.Parent==self then table.insert(out,c) end end return out end
 function n:GetDescendants() local out={} local function visit(o) for _,c in ipairs(o:GetChildren()) do table.insert(out,c) visit(c) end end visit(self) return out end
 function n:Destroy() self.Parent=nil self.destroyed=true end
 return n
end
function rig(r15)
 local char=node('Character','Model')
 local root=node('HumanoidRootPart','Part',char);root.Size=Vector3.new(2,2,1)
 local torso=node(r15 and 'UpperTorso' or 'Torso','Part',char);torso.Size=Vector3.new(2,2,1)
 local arm=node(r15 and 'LeftUpperArm' or 'Left Arm',r15 and 'MeshPart' or 'Part',char);arm.Size=Vector3.new(1,2,1)
 local joint=node('LeftShoulder','Motor6D',r15 and arm or torso)
 joint.Part0=torso;joint.Part1=arm;joint.C0=CFrame.new(2,3,4)
 local accessory=node('Hat','Accessory',char);local handle=node('Handle','Part',accessory);handle.Size=Vector3.new(1,1,1)
 return char,arm,joint,root
end
LocalPlayer={CharacterRemoving=signal(),CharacterAdded=signal()}
char,arm,joint,root=rig(false);LocalPlayer.Character=char
Gui=node('Gui','ScreenGui');PlayerTab={};T={Accent='purple'};controls={};cleanups={}
function new(kind,props,parent) local o=node(kind,kind,parent) for k,v in pairs(props) do o[k]=v end outline=o return o end
function Section() return {} end
function Collapse() return {} end
function InfoRow(_,text) info={Text=text};return info end
function bind(s,fn) s:Connect(fn) end
function onUnload(fn) table.insert(cleanups,fn) end
function Toggle(_,name,initial,cb)
 local o={value=initial};function o.Set(v) o.value=v end;function o.Fire(v) o.value=v;cb(v) end;controls[name]=o;return o
end
function Button(_,name,action,cb) controls[name]={Fire=cb} end
function Slider(_,name,low,high,initial,cb)
 local o={value=initial};function o.SetSilent(v) o.value=v end;function o.Fire(v) cb(v) end;controls[name]=o;return o
end
function Dropdown(_,name,options,initial,cb)
 local o={options=options};function o.SetOptions(v) o.options=v end;function o.Set(i,silent) o.index=i;if not silent then cb(i) end end
 controls[name]=o;return o
end
function selectArm()
 local o=controls['Body Part'];for i,n in ipairs(o.options) do if n==arm.Name then o.Set(i,false);return end end
 error('arm missing')
end
'''

class BodyEditorTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(FIXTURE)
        self.lua.execute(BLOCK)

    def check(self, code):
        self.lua.execute(code)

    def test_disabled_edits_and_only_own_direct_parts(self):
        self.check('''selectArm();controls['Width %'].Fire(200);assert(arm.Size.X==1)
        for _,name in ipairs(controls['Body Part'].options) do assert(name~='HumanoidRootPart' and name~='Handle') end
        assert(outline.Visible==false)
        ''')

    def test_size_offset_rotation_are_relative_and_reset(self):
        self.check('''controls['Enable Body Editing'].Fire(true);selectArm()
        controls['Width %'].Fire(200);controls['Height %'].Fire(150)
        assert(arm.Size.X==2 and arm.Size.Y==3)
        controls['Offset X'].Fire(20);assert(joint.C0.X==4 and joint.C0.Y==3)
        controls['Offset X'].Fire(30);assert(joint.C0.X==5)
        controls['Rotate X'].Fire(90);assert(math.abs(joint.C0.RX-math.pi/2)<0.001)
        assert(outline.Adornee==arm)
        controls['Reset Selected Body Part'].Fire()
        assert(arm.Size.X==1 and arm.Size.Y==2 and joint.C0.X==2)
        assert(controls['Width %'].value==100 and controls['Offset X'].value==0)
        ''')

    def test_transferred_part_is_not_modified(self):
        self.check('''controls['Enable Body Editing'].Fire(true);selectArm()
        local other=node('OtherPlayer','Model');arm.Parent=other
        controls['Width %'].Fire(200);assert(arm.Size.X==1)
        arm.Parent=char;controls['Width %'].Fire(200);assert(arm.Size.X==2)
        arm.Parent=other;controls['Reset All Body Parts'].Fire();assert(arm.Size.X==2)
        ''')

    def test_disable_unload_and_respawn_restore_edits(self):
        self.check('''controls['Enable Body Editing'].Fire(true);selectArm();controls['Width %'].Fire(200)
        controls['Enable Body Editing'].Fire(false);assert(arm.Size.X==1)
        controls['Enable Body Editing'].Fire(true);selectArm();controls['Offset Y'].Fire(20)
        LocalPlayer.CharacterRemoving:Fire(char);assert(joint.C0.Y==3);assert(outline.Adornee==nil)
        char,arm,joint,root=rig(true);LocalPlayer.Character=char;LocalPlayer.CharacterAdded:Fire(char)
        assert(controls['Enable Body Editing'].value==false)
        selectArm();controls['Width %'].Fire(200);assert(arm.Size.X==1)
        controls['Enable Body Editing'].Fire(true);selectArm();controls['Depth %'].Fire(250)
        assert(arm.Size.Z==2.5)
        for _,fn in ipairs(cleanups) do fn() end
        assert(arm.Size.Z==1 and outline.destroyed)
        ''')

    def test_no_joint_still_allows_size_without_detaching(self):
        self.check('''joint.Parent=nil;controls['Enable Body Editing'].Fire(true);selectArm()
        controls['Height %'].Fire(200);assert(arm.Size.Y==4)
        assert(string.find(info.Text,'no Motor6D'))
        assert(arm.Parent==char and root.Size.X==2)
        controls['Reset All Body Parts'].Fire();assert(arm.Size.Y==2)
        ''')

if __name__=='__main__':
    unittest.main()
