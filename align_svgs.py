import re

TARGET_WIDTH = 65
TEXT_X = 415
SVG_WIDTH = 1160
SVG_HEIGHT = 530

def make_dotted_row(y, prefix, key_parts, dots_id, val_id, value):
    key_text = prefix + ''.join(t for t, _ in key_parts)
    key_xml = f'<tspan x="{TEXT_X}" y="{y}" class="cc">{prefix}</tspan>'
    for t, cls in key_parts:
        if cls:
            key_xml += f'<tspan class="{cls}">{t}</tspan>'
        else:
            key_xml += t
    
    val_text = value
    val_xml_esc = value.replace('&', '&amp;')
    if val_id:
        val_xml = f'<tspan class="value" id="{val_id}">{val_xml_esc}</tspan>'
    else:
        val_xml = f'<tspan class="value">{val_xml_esc}</tspan>'
        
    needed = TARGET_WIDTH - len(key_text) - len(val_text)
    assert needed >= 3, f"Not enough room for row y={y} {key_text}: needed {needed}"
    num_dots = needed - 2
    dots_str = ' ' + ('.' * num_dots) + ' '
    if dots_id:
        dots_xml = f'<tspan class="cc" id="{dots_id}">{dots_str}</tspan>'
    else:
        dots_xml = f'<tspan class="cc">{dots_str}</tspan>'
        
    line_xml = f'{key_xml}{dots_xml}{val_xml}'
    pure_text = key_text + dots_str + val_text
    assert len(pure_text) == TARGET_WIDTH, f"Row y={y} len {len(pure_text)} != {TARGET_WIDTH}"
    return line_xml

def make_header_row(y, title):
    used = len(title) + 2 + 3 # title + ' -' + '-—-'
    dashes_count = TARGET_WIDTH - used
    dashes = '—' * dashes_count
    line_xml = f'<tspan x="{TEXT_X}" y="{y}">{title}</tspan> -{dashes}-—-'
    pure_text = f'{title} -{dashes}-—-'
    assert len(pure_text) == TARGET_WIDTH, f"Header len {len(pure_text)} != {TARGET_WIDTH}"
    return line_xml

def generate_terminal_block(fill_color):
    rows = [
        make_header_row(30, 'arjun@simpliarjun'),
        make_dotted_row(50, '. ', [('OS', 'key'), (':', None)], None, None, 'macOS, iOS, Android, Linux'),
        make_dotted_row(70, '. ', [('Uptime', 'key'), (':', None)], 'age_data_dots', 'age_data', '23 years, 10 months, 3 days'),
        make_dotted_row(90, '. ', [('Host', 'key'), (':', None)], None, None, 'Full-Stack & iOS Engineer'),
        make_dotted_row(110, '. ', [('Kernel', 'key'), (':', None)], None, None, 'MERN Stack, SwiftUI & FastAPI'),
        make_dotted_row(130, '. ', [('IDE', 'key'), (':', None)], None, None, 'Antigravity, Xcode, VSCode'),
        f'<tspan x="{TEXT_X}" y="150" class="cc">. </tspan>',
        make_dotted_row(170, '. ', [('Languages', 'key'), ('.', None), ('Programming', 'key'), (':', None)], None, None, 'TypeScript, JavaScript, Swift, Python'),
        make_dotted_row(190, '. ', [('Languages', 'key'), ('.', None), ('Computer', 'key'), (':', None)], None, None, 'React, Next.js, Node.js, TailwindCSS, SQL'),
        make_dotted_row(210, '. ', [('Languages', 'key'), ('.', None), ('Real', 'key'), (':', None)], None, None, 'English, Hindi'),
        f'<tspan x="{TEXT_X}" y="230" class="cc">. </tspan>',
        make_dotted_row(250, '. ', [('Hobbies', 'key'), ('.', None), ('Software', 'key'), (':', None)], None, None, 'Responsive UI, Seamless UX, Scalable Apps'),
        make_dotted_row(270, '. ', [('Hobbies', 'key'), ('.', None), ('Hardware', 'key'), (':', None)], None, None, 'iOS Ecosystem, Local-First Architecture'),
        make_header_row(310, '- Contact'),
        make_dotted_row(330, '. ', [('Email', 'key'), ('.', None), ('Personal', 'key'), (':', None)], None, None, 'contact.arjito@gmail.com'),
        make_dotted_row(350, '. ', [('LinkedIn', 'key'), (':', None)], None, None, 'arjun-gupta-simpli'),
        make_dotted_row(370, '. ', [('Twitter', 'key'), (':', None)], None, None, 'simpliarjun'),
        make_dotted_row(390, '. ', [('Discord', 'key'), (':', None)], None, None, 'simpliarjun'),
        make_dotted_row(410, '. ', [('GitHub', 'key'), (':', None)], None, None, 'simpliarjun'),
        make_header_row(450, '- GitHub Stats'),
        f'<tspan x="{TEXT_X}" y="470" class="cc">. </tspan><tspan class="key">Repos</tspan>:<tspan class="cc" id="repo_data_dots"> .... </tspan><tspan class="value" id="repo_data">95</tspan> {{<tspan class="key">Contributed</tspan>: <tspan class="value" id="contrib_data">133</tspan>}} | <tspan class="key">Stars</tspan>:<tspan class="cc" id="star_data_dots"> ................ </tspan><tspan class="value" id="star_data">342</tspan>',
        f'<tspan x="{TEXT_X}" y="490" class="cc">. </tspan><tspan class="key">Commmits</tspan>:<tspan class="cc" id="commit_data_dots"> ...................... </tspan><tspan class="value" id="commit_data">2,116</tspan> | <tspan class="key">Followers</tspan>:<tspan class="cc" id="follower_data_dots"> ....... </tspan><tspan class="value" id="follower_data">196</tspan>',
        f'<tspan x="{TEXT_X}" y="510" class="cc">. </tspan><tspan class="key">Lines of Code on GitHub</tspan>:<tspan class="cc" id="loc_data_dots"> ..... </tspan><tspan class="value" id="loc_data">446,276</tspan> ( <tspan class="addColor" id="loc_add">523,178</tspan><tspan class="addColor">++</tspan>, <tspan id="loc_del_dots"> </tspan><tspan class="delColor" id="loc_del">76,902</tspan><tspan class="delColor">--</tspan> )'
    ]
    return f'<text x="{TEXT_X}" y="30" fill="{fill_color}">\n' + '\n'.join(rows) + '\n</text>'

def update_svg(filename, fill_color):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update <svg> tag with viewBox and dimensions
    svg_tag = f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" width="{SVG_WIDTH}px" height="{SVG_HEIGHT}px" font-size="16px">'
    content = re.sub(r'<svg\s+[^>]*>', svg_tag, content, count=1)
    
    # Update <rect> tag
    content = re.sub(r'<rect\s+width="[^"]*"\s+height="[^"]*"', f'<rect width="{SVG_WIDTH}px" height="{SVG_HEIGHT}px"', content, count=1)
    
    # Trim trailing whitespace in ascii art lines
    def trim_ascii(m):
        prefix = m.group(1)
        text = m.group(2).rstrip()
        return f'{prefix}{text}</tspan>'
    content = re.sub(r'(<tspan\s+x="15"\s+y="\d+">)(.*?)</tspan>', trim_ascii, content)
    
    new_block = generate_terminal_block(fill_color)
    pattern = r'<text x="\d+"\s+y="30"\s+fill="[^"]*">.*?</text>'
    updated, count = re.subn(pattern, new_block, content, flags=re.DOTALL)
    assert count == 1, f"Failed to replace terminal block in {filename}"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f"Updated {filename} successfully with width={SVG_WIDTH} and text_x={TEXT_X}.")

if __name__ == '__main__':
    update_svg('dark_mode.svg', '#c9d1d9')
    update_svg('light_mode.svg', '#24292f')
