"""Test the actual shared hub loader with executor/network/compiler doubles."""
from pathlib import Path
import unittest
from lupa import LuaRuntime

SOURCE = Path(__file__).resolve().parents[1].joinpath('Soloshub.txt').read_text()
LOADER = SOURCE[SOURCE.index('\tfunction Hub.loadGameModule(g)'):SOURCE.index('\n\t-- ------------------------------------------------------------ game list')]
URLS = SOURCE[SOURCE.index('\tHub.ModuleURLs = {'):SOURCE.index('\n\n\t-- everything a game script')]

class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''Hub={};S={};T={};C={};warn=function(s) lastWarning=s end
        requestCalls=0;httpCalls=0;compiled=0;initialized=0
        request=function(options) requestCalls=requestCalls+1;lastURL=options.Url;return {StatusCode=200,Body='valid module'} end
        game={HttpGet=function(self,url,noCache) httpCalls=httpCalls+1;lastURL=url;return 'fallback module' end}
        loadstring=function(source,name)
          compiled=compiled+1;lastSource=source;lastChunk=name
          return function(h,s,t,c) assert(h==Hub and s==S and t==T and c==C);initialized=initialized+1 end
        end
        ''')
        self.lua.execute(URLS+LOADER)

    def test_all_six_games_use_own_urls_and_hub_api(self):
        self.lua.execute('''for _,id in ipairs({'mm2','arsenal','pf','lt2','doomspire','bab'}) do
          assert(Hub.loadGameModule({id=id,name=id}))
          assert(lastURL==Hub.ModuleURLs[id]);assert(lastChunk=='='..id)
        end
        assert(requestCalls==6 and httpCalls==0 and initialized==6)
        ''')

    def test_http_error_uses_httpget_fallback(self):
        self.lua.execute('''request=function() error('HTTP 403') end
        assert(Hub.loadGameModule({id='lt2',name='Lumber Tycoon 2'}))
        assert(httpCalls==1 and initialized==1 and lastSource=='fallback module')
        assert(Hub.LastModuleError==nil)
        ''')

    def test_bad_responses_and_missing_request_fall_back(self):
        self.lua.execute('''for _,response in ipairs({{},'not a table',{StatusCode=404,Body='not found'},{StatusCode=200,Body='  '},{Success=false,Body='denied'}}) do
          request=function() return response end
          assert(Hub.loadGameModule({id='mm2'}))
        end
        request=nil;assert(Hub.loadGameModule({id='mm2'}))
        assert(httpCalls==6)
        ''')

    def test_both_methods_fail_preserves_actual_error(self):
        self.lua.execute('''request=function() error('HTTP 403') end
        game.HttpGet=function() error('HttpGet blocked') end
        local ok,err=Hub.loadGameModule({id='mm2',name='Murder Mystery 2'})
        assert(not ok and string.find(err,'HTTP 403') and string.find(err,'HttpGet blocked'))
        assert(Hub.LastModuleError.id=='mm2' and Hub.LastModuleError.message==err)
        assert(compiled==0 and initialized==0)
        ''')

    def test_compile_and_initialization_failures_are_distinguished(self):
        self.lua.execute('''loadstring=function() return nil,'syntax problem' end
        local ok,err=Hub.loadGameModule({id='pf'});assert(not ok and string.find(err,'compile failed'))
        loadstring=function() error('compiler threw') end
        ok,err=Hub.loadGameModule({id='pf'});assert(not ok and string.find(err,'compiler threw'))
        loadstring=function() return function() error('game API missing') end end
        ok,err=Hub.loadGameModule({id='pf'});assert(not ok and string.find(err,'module initialization failed'))
        ''')

if __name__=='__main__': unittest.main()
