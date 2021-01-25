import ipyvuetify as v 

from component import parameter as pm

class MatrixInput(v.Html):
    
    VALUES = {
        '+': (1, v.theme.themes.dark.success),  
        '': (0, v.theme.themes.dark.primary),
        '-': (-1, v.theme.themes.dark.error)
    }
    
    
    def __init__(self, line, column, io, default_value, output):
        
        # get the io for dynamic modification
        self.io = io
        
        # get the line and column of the td in the matrix
        self.column = column
        self.line = line
        
        # get the output
        self.output = output
        
        self.val = v.Select(dense = True, color = 'white', items = [*self.VALUES], class_='ma-1', v_model = default_value)
        
        super().__init__(
            style_ = f'background-color: {v.theme.themes.dark.primary}',
            tag = 'td',
            children = [self.val]
        )
        
        # connect the color to the value
        self.val.observe(self.color_change, 'v_model')
        
    def color_change(self, change):
            
        val, color = self.VALUES[change['new']]
        
        self.style_ = f'background-color: {color}'
        self.io.transition_matrix[self.line][self.column] = val
        
        self.output.add_msg('You have changed your transition matrix')
            
        return 
    
class TransitionMatrix(v.SimpleTable):
    
    CLASSES = ['Forest', 'Grassland', 'Cropland', 'Wetland', 'Artificial area', 'Bare land', 'water body']
    
    DECODE = {1: '+', 0: '', -1:'-'}
    
    def __init__(self, io, output):
        
        # create a header        
        header = [
            v.Html(
                tag = 'tr', 
                children = (
                    [v.Html(tag = 'th', children = [''])] 
                    + [v.Html(tag = 'th', children = [class_]) for class_ in self.CLASSES]
                )
            )
        ]
        
        # create a row
        rows = []
        for i, baseline in enumerate(self.CLASSES):
            
            inputs = []
            for j, target in enumerate(self.CLASSES):
                # create a input with default matrix value
                default_value = self.DECODE[pm.default_trans_matrix[i][j]]
                matrix_input = MatrixInput(i, j, io, default_value, output)
                matrix_input.color_change({'new': default_value})
                
                input_ = v.Html(tag='td', class_='ma-0 pa-0', children=[matrix_input])
                inputs.append(input_)
                
            row = v.Html(tag='tr', children=(
                [v.Html(tag='th', children=[baseline])] 
                + inputs
            ))
            rows.append(row)
                   
        # create the simple table 
        super().__init__(
            children = [
                v.Html(tag = 'tbody', children = header + rows)
            ]
        )